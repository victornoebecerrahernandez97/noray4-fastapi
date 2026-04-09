"""
WebSocket Bridge — retransmite mensajes entre clientes Angular y el broker MQTT.

Flujo:
  1. Cliente Angular abre WS en /ws/{sala_id}?token=<jwt>
  2. Bridge valida JWT, resuelve rider, acepta la conexión
  3. Suscribe al patrón noray4/{sala_id}/# via mqtt_gateway
  4. Publica presencia "online" al broker
  5. Dos tareas concurrentes:
       - broker → WS: saca de asyncio.Queue y envía al cliente
       - WS → broker: recibe JSON del cliente y publica al topic indicado
  6. Al desconectar: publica presencia "offline", limpia suscripción
"""
import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from shared.auth import verify_token
from shared.database import get_riders_collection
from ms_realtime.mqtt_client import TOPIC_PRESENCIA, mqtt_gateway

logger = logging.getLogger("noray4.ws")


async def endpoint(websocket: WebSocket, sala_id: str) -> None:
    # ------------------------------------------------------------------
    # 1. Validar JWT desde query param
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 2. Resolver perfil de rider
    # ------------------------------------------------------------------
    riders_col = get_riders_collection()
    rider = await riders_col.find_one({"user_id": user_id})
    if not rider:
        await websocket.close(code=4003, reason="Perfil de rider requerido")
        return

    rider_id = str(rider["_id"])
    display_name = rider.get("display_name", "Rider")

    # ------------------------------------------------------------------
    # 3. Aceptar conexión y configurar suscripción MQTT
    # ------------------------------------------------------------------
    await websocket.accept()

    topic_pattern = f"noray4/{sala_id}/#"
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    mqtt_gateway.add_queue(topic_pattern, queue)

    # ------------------------------------------------------------------
    # 4. Publicar presencia online
    # ------------------------------------------------------------------
    presence_topic = TOPIC_PRESENCIA.format(sala_id=sala_id)
    mqtt_gateway.publish(presence_topic, {
        "rider_id": rider_id,
        "display_name": display_name,
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
    })

    logger.info("WS conectado — sala=%s rider=%s", sala_id, rider_id)

    # ------------------------------------------------------------------
    # 5. Tareas bidireccionales
    # ------------------------------------------------------------------

    async def broker_to_ws() -> None:
        """Reenvía mensajes del broker MQTT al cliente WebSocket."""
        while True:
            envelope = await queue.get()
            try:
                await websocket.send_json(envelope)
            except Exception:
                break

    async def ws_to_broker() -> None:
        """Reenvía mensajes del cliente WebSocket al broker MQTT."""
        while True:
            try:
                data = await websocket.receive_json()
                # Espera: {"topic": "noray4/{sala_id}/...", "payload": {...}}
                # Si no viene topic, publica en el topic de eventos de la sala
                topic = data.get("topic") or f"noray4/{sala_id}/eventos"
                mqtt_gateway.publish(topic, data.get("payload", data))
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WS receive error: %s", exc)
                break

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
        # ------------------------------------------------------------------
        # 6. Limpieza al desconectar
        # ------------------------------------------------------------------
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
