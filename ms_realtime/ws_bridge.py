"""
WebSocket Bridge — retransmite mensajes entre clientes y broker MQTT.
Audio PTT: relay directo WS→WS sin pasar por MQTT (baja latencia).

Flujo:
  1. Cliente abre WS en /ws/{sala_id}?token=<jwt>
  2. Bridge valida JWT, resuelve rider, acepta la conexión
  3. Suscribe al patrón noray4/{sala_id}/# via mqtt_gateway
  4. Registra la conexión en WSConnectionStore para relay de audio
  5. Publica presencia "online" al broker
  6. Dos tareas concurrentes:
       - broker → WS: saca de asyncio.Queue y envía al cliente
       - WS → broker: recibe JSON del cliente y:
           * Si type="audio": relay directo WS→WS (bypass MQTT)
           * Otros: publica al topic MQTT indicado
  7. Al desconectar: publica presencia "offline", limpia todo
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect

from shared.auth import verify_token
from shared.database import get_riders_collection
from ms_realtime.mqtt_client import TOPIC_PRESENCIA, mqtt_gateway
from ms_voice.ptt_store import ptt_store

logger = logging.getLogger("noray4.ws")

# ---------------------------------------------------------------------------
# Rate limiting: máx 50 frames de audio por segundo por rider
# ---------------------------------------------------------------------------
_AUDIO_MAX_FPS = 50
_AUDIO_WINDOW_S = 1.0


# ---------------------------------------------------------------------------
# WSConnectionStore — registro de conexiones WS activas por sala
# ---------------------------------------------------------------------------

class _WSConn:
    """Conexión activa con estado de rate-limit integrado."""
    __slots__ = ("ws", "rider_id", "display_name", "_count", "_win_start")

    def __init__(self, ws: WebSocket, rider_id: str, display_name: str) -> None:
        self.ws = ws
        self.rider_id = rider_id
        self.display_name = display_name
        self._count = 0
        self._win_start = time.monotonic()

    def allow_frame(self) -> bool:
        """True si el frame supera el rate limit (50 fps). Ventana deslizante."""
        now = time.monotonic()
        if now - self._win_start >= _AUDIO_WINDOW_S:
            self._count = 0
            self._win_start = now
        self._count += 1
        return self._count <= _AUDIO_MAX_FPS


class WSConnectionStore:
    """Registro en memoria de WebSockets activos agrupados por sala."""

    def __init__(self) -> None:
        self._rooms: Dict[str, List[_WSConn]] = {}

    def register(self, sala_id: str, conn: _WSConn) -> None:
        self._rooms.setdefault(sala_id, []).append(conn)

    def unregister(self, sala_id: str, conn: _WSConn) -> None:
        conns = self._rooms.get(sala_id, [])
        if conn in conns:
            conns.remove(conn)
        if not conns:
            self._rooms.pop(sala_id, None)

    async def broadcast_audio(
        self, sala_id: str, sender_rider_id: str, frame: dict
    ) -> None:
        """Envía frame a todos los clientes de la sala excepto el emisor."""
        for conn in list(self._rooms.get(sala_id, [])):
            if conn.rider_id == sender_rider_id:
                continue
            try:
                await conn.ws.send_json(frame)
            except Exception:
                pass  # Conexión muerta — se limpiará en su propia tarea


ws_store = WSConnectionStore()


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

async def endpoint(websocket: WebSocket, sala_id: str) -> None:
    # 1. Validar JWT desde query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token requerido")
        return

    try:
        payload = verify_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("sub ausente")
    except Exception:
        await websocket.close(code=4001, reason="Token inválido o expirado")
        return

    # 2. Resolver perfil de rider
    riders_col = get_riders_collection()
    rider = await riders_col.find_one({"user_id": user_id})
    if not rider:
        await websocket.close(code=4003, reason="Perfil de rider requerido")
        return

    rider_id = str(rider["_id"])
    display_name = rider.get("display_name", "Rider")

    # 3. Aceptar conexión, registrar en stores MQTT y WS
    await websocket.accept()

    topic_pattern = f"noray4/{sala_id}/#"
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    mqtt_gateway.add_queue(topic_pattern, queue)

    conn = _WSConn(websocket, rider_id, display_name)
    ws_store.register(sala_id, conn)

    # 4. Presencia online
    presence_topic = TOPIC_PRESENCIA.format(sala_id=sala_id)
    mqtt_gateway.publish(presence_topic, {
        "rider_id": rider_id,
        "display_name": display_name,
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
    })

    logger.info("WS conectado — sala=%s rider=%s", sala_id, rider_id)

    # 5. Tareas bidireccionales

    async def broker_to_ws() -> None:
        """Reenvía mensajes del broker MQTT al cliente WebSocket."""
        while True:
            envelope = await queue.get()
            try:
                await websocket.send_json(envelope)
            except Exception:
                break

    async def ws_to_broker() -> None:
        """Recibe mensajes del cliente. Audio → relay WS. Resto → MQTT."""
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WS receive error: %s", exc)
                break

            # ---- Audio relay directo WS→WS (sin pasar por MQTT) ----
            if data.get("type") == "audio":
                canal_id = data.get("canal_id", "")
                state = ptt_store.get_state(canal_id)
                # Solo el speaker activo puede emitir frames
                if not state or not state.is_speaking or state.speaker_id != rider_id:
                    continue
                # Rate limit suave (50 fps)
                if not conn.allow_frame():
                    continue
                # Enriquecer frame con identidad antes de retransmitir
                relay = {**data, "rider_id": rider_id, "display_name": display_name}
                await ws_store.broadcast_audio(sala_id, rider_id, relay)
                continue

            # ---- Mensajes normales → MQTT ----
            topic = data.get("topic") or f"noray4/{sala_id}/eventos"
            mqtt_gateway.publish(topic, data.get("payload", data))

    tasks = [
        asyncio.create_task(broker_to_ws()),
        asyncio.create_task(ws_to_broker()),
    ]

    try:
        _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except Exception as exc:
        logger.debug("WS session error: %s", exc)
    finally:
        # 6. Limpieza al desconectar
        ws_store.unregister(sala_id, conn)
        mqtt_gateway.remove_queue(topic_pattern, queue)
        mqtt_gateway.publish(presence_topic, {
            "rider_id": rider_id,
            "display_name": display_name,
            "status": "offline",
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info("WS desconectado — sala=%s rider=%s", sala_id, rider_id)
        try:
            await websocket.close()
        except Exception:
            pass
