"""
MQTT Gateway — async wrapper sobre paho-mqtt 2.x con TLS para HiveMQ Cloud.

Arquitectura:
- paho-mqtt corre en un hilo de red separado (loop_start)
- Los mensajes entrantes se enrutan a asyncio.Queue registradas por topic pattern
- Los publishers HTTP/WS llaman a publish() desde el hilo asyncio principal
"""
import asyncio
import json
import logging
import secrets
import ssl
from typing import Dict, List

import paho.mqtt.client as mqtt

from shared.config import settings

logger = logging.getLogger("noray4.mqtt")

# ---------------------------------------------------------------------------
# Topic templates — usar con .format(sala_id=...)
# ---------------------------------------------------------------------------
TOPIC_UBICACION = "noray4/{sala_id}/ubicacion"
TOPIC_CHAT = "noray4/{sala_id}/chat"
TOPIC_VOZ = "noray4/{sala_id}/voz"
TOPIC_EVENTOS = "noray4/{sala_id}/eventos"
TOPIC_PRESENCIA = "noray4/{sala_id}/presencia"


class MQTTGateway:
    """Singleton que gestiona la conexión MQTT y el enrutamiento de mensajes."""

    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = False
        # topic_pattern → lista de Queue que reciben mensajes
        self._queues: Dict[str, List[asyncio.Queue]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        if not settings.HIVEMQ_HOST:
            logger.warning("HIVEMQ_HOST no configurado — MQTT gateway deshabilitado")
            return

        self._loop = asyncio.get_event_loop()

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"noray4-api-{secrets.token_hex(4)}",
        )
        self._client.username_pw_set(settings.HIVEMQ_USER, settings.HIVEMQ_PASSWORD)
        self._client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

        # Reconexión automática con backoff (1s → 30s máx, 3 ciclos antes de loguear warning)
        self._client.reconnect_delay_set(min_delay=1, max_delay=10)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # connect_async es no-bloqueante; loop_start inicia el hilo de red
        self._client.connect_async(settings.HIVEMQ_HOST, settings.HIVEMQ_PORT, keepalive=60)
        self._client.loop_start()

        # Espera hasta 10 s a que se establezca la conexión MQTT
        for _ in range(20):
            if self._connected:
                return
            await asyncio.sleep(0.5)

        logger.error(
            "MQTT: timeout de conexión a %s:%s — el servicio arranca sin MQTT",
            settings.HIVEMQ_HOST,
            settings.HIVEMQ_PORT,
        )

    async def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("MQTT desconectado")

    # ------------------------------------------------------------------
    # Callbacks de paho (ejecutan en el hilo de red de paho, no en asyncio)
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error("MQTT conexión rechazada — %s", reason_code)
            return

        self._connected = True
        logger.info("MQTT conectado a %s:%s", settings.HIVEMQ_HOST, settings.HIVEMQ_PORT)

        # Re-suscribir tras reconexión (los topics se pierden al caer la conexión)
        for pattern, queues in self._queues.items():
            if queues:
                client.subscribe(pattern, qos=1)
                logger.debug("MQTT re-suscrito a %s", pattern)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self._connected = False
        logger.warning("MQTT desconectado — %s (reconectando automáticamente…)", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        topic = message.topic
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            payload = {"raw": message.payload.decode("utf-8", errors="replace")}

        if self._loop is None or self._loop.is_closed():
            return

        envelope = {"topic": topic, "payload": payload}

        for pattern, queues in list(self._queues.items()):
            if _topic_matches(pattern, topic):
                for q in list(queues):
                    asyncio.run_coroutine_threadsafe(q.put(envelope), self._loop)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, payload: dict) -> None:
        """Publica un dict como JSON. Thread-safe. No-op si no hay conexión."""
        if not self._client or not self._connected:
            logger.debug("MQTT no conectado — publish ignorado: %s", topic)
            return
        self._client.publish(topic, json.dumps(payload, default=str), qos=1)

    def add_queue(self, topic_pattern: str, queue: asyncio.Queue) -> None:
        """Registra una Queue para recibir mensajes de un topic pattern."""
        self._queues.setdefault(topic_pattern, []).append(queue)
        if self._client and self._connected:
            self._client.subscribe(topic_pattern, qos=1)
            logger.debug("MQTT suscrito a %s", topic_pattern)

    def remove_queue(self, topic_pattern: str, queue: asyncio.Queue) -> None:
        """Elimina una Queue. Si no quedan queues para el pattern, desuscribe."""
        queues = self._queues.get(topic_pattern, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._queues.pop(topic_pattern, None)
            if self._client and self._connected:
                self._client.unsubscribe(topic_pattern)
                logger.debug("MQTT desuscrito de %s", topic_pattern)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _topic_matches(pattern: str, topic: str) -> bool:
    """Matching de topics MQTT con soporte de wildcards + y #."""
    if pattern == topic:
        return True
    p_parts = pattern.split("/")
    t_parts = topic.split("/")
    if p_parts[-1] == "#":
        prefix = p_parts[:-1]
        return t_parts[: len(prefix)] == prefix
    if len(p_parts) != len(t_parts):
        return False
    return all(pp == "+" or pp == tp for pp, tp in zip(p_parts, t_parts))


# ---------------------------------------------------------------------------
# Instancia singleton — importada por router, ws_bridge y main
# ---------------------------------------------------------------------------
mqtt_gateway = MQTTGateway()
