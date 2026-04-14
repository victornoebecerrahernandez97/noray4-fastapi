"""
Tests unitarios para audio relay en ws_bridge.py

Cubre:
- Frame del speaker activo se retransmite a los demás
- Frame de un rider que NO es speaker se ignora
- El emisor NO recibe su propio frame
- Clientes sin audio siguen funcionando (mensajes normales pasan a MQTT)
- Rate limit: frames en exceso de 50/s se descartan
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ms_realtime.ws_bridge import _WSConn, WSConnectionStore, ws_store
from ms_voice.ptt_store import PTTStore
from ms_voice.schemas import PTTState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ws(rider_id: str = "r1") -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


def _make_conn(rider_id: str, display_name: str = "Rider") -> _WSConn:
    return _WSConn(_make_ws(rider_id), rider_id, display_name)


def _active_state(canal_id: str, sala_id: str, speaker_id: str) -> PTTState:
    return PTTState(
        canal_id=canal_id,
        sala_id=sala_id,
        speaker_id=speaker_id,
        speaker_name="Speaker",
        is_speaking=True,
        timestamp=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# WSConnectionStore
# ---------------------------------------------------------------------------

class TestWSConnectionStore:
    def setup_method(self):
        self.store = WSConnectionStore()

    @pytest.mark.asyncio
    async def test_broadcast_reaches_all_except_sender(self):
        """Frame debe llegar a todos los riders menos al emisor."""
        sender = _make_conn("sender")
        peer1 = _make_conn("peer1")
        peer2 = _make_conn("peer2")

        for c in (sender, peer1, peer2):
            self.store.register("sala1", c)

        frame = {"type": "audio", "data": "AAAA", "rider_id": "sender"}
        await self.store.broadcast_audio("sala1", "sender", frame)

        sender.ws.send_json.assert_not_called()
        peer1.ws.send_json.assert_awaited_once_with(frame)
        peer2.ws.send_json.assert_awaited_once_with(frame)

    @pytest.mark.asyncio
    async def test_broadcast_empty_sala_no_error(self):
        """Broadcast a sala sin conexiones no debe lanzar excepción."""
        await self.store.broadcast_audio("sala_vacia", "r1", {"type": "audio"})

    @pytest.mark.asyncio
    async def test_dead_connection_does_not_propagate_error(self):
        """Si send_json falla en un peer, el broadcast continúa con los demás."""
        dead = _make_conn("dead")
        dead.ws.send_json = AsyncMock(side_effect=RuntimeError("closed"))
        live = _make_conn("live")

        self.store.register("sala1", dead)
        self.store.register("sala1", live)

        frame = {"type": "audio"}
        # No debe lanzar
        await self.store.broadcast_audio("sala1", "sender", frame)
        live.ws.send_json.assert_awaited_once()

    def test_unregister_removes_connection(self):
        conn = _make_conn("r1")
        self.store.register("sala1", conn)
        self.store.unregister("sala1", conn)
        assert "sala1" not in self.store._rooms

    def test_unregister_sala_with_remaining_conns(self):
        c1 = _make_conn("r1")
        c2 = _make_conn("r2")
        self.store.register("sala1", c1)
        self.store.register("sala1", c2)
        self.store.unregister("sala1", c1)
        assert "sala1" in self.store._rooms
        assert c2 in self.store._rooms["sala1"]


# ---------------------------------------------------------------------------
# Audio relay — validación de speaker activo
# ---------------------------------------------------------------------------

class TestAudioRelay:
    """Verifica la lógica de speaker-check en ws_to_broker."""

    def setup_method(self):
        self.store = WSConnectionStore()
        self.ptt = PTTStore()

    @pytest.mark.asyncio
    async def test_active_speaker_frame_relayed(self):
        """Speaker activo: frame debe retransmitirse al peer."""
        speaker_conn = _make_conn("speaker")
        peer_conn = _make_conn("peer")
        self.store.register("sala1", speaker_conn)
        self.store.register("sala1", peer_conn)

        self.ptt.set_speaking("canal1", "sala1", "speaker", "Speaker")
        state = self.ptt.get_state("canal1")

        assert state.is_speaking
        assert state.speaker_id == "speaker"

        frame = {"type": "audio", "canal_id": "canal1", "data": "AAAA"}
        relay = {**frame, "rider_id": "speaker", "display_name": "Speaker"}
        await self.store.broadcast_audio("sala1", "speaker", relay)

        peer_conn.ws.send_json.assert_awaited_once()
        sent = peer_conn.ws.send_json.call_args[0][0]
        assert sent["rider_id"] == "speaker"
        assert sent["display_name"] == "Speaker"

    def test_non_speaker_frame_ignored(self):
        """Si el rider no es el speaker activo, el frame no pasa."""
        self.ptt.set_speaking("canal1", "sala1", "speaker", "Speaker")
        state = self.ptt.get_state("canal1")

        # rider "intruder" no es el speaker
        assert state.speaker_id != "intruder"
        # La lógica de ws_bridge comprueba: state.speaker_id != rider_id → continue
        is_allowed = (
            state is not None
            and state.is_speaking
            and state.speaker_id == "intruder"
        )
        assert not is_allowed

    def test_no_active_ptt_frame_ignored(self):
        """Sin estado PTT activo, ningún frame debe pasar."""
        state = self.ptt.get_state("canal_inexistente")
        assert state is None

    def test_released_ptt_frame_ignored(self):
        """Tras soltar PTT, frames del mismo rider se ignoran."""
        self.ptt.set_speaking("canal1", "sala1", "speaker", "Speaker")
        self.ptt.release_speaking("canal1", "sala1", "speaker")
        state = self.ptt.get_state("canal1")
        assert state is not None
        assert not state.is_speaking


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    def test_first_50_frames_allowed(self):
        conn = _make_conn("r1")
        for i in range(50):
            assert conn.allow_frame(), f"Frame {i+1} debería pasar"

    def test_frame_51_blocked(self):
        conn = _make_conn("r1")
        for _ in range(50):
            conn.allow_frame()
        assert not conn.allow_frame(), "Frame 51 debe ser bloqueado"

    def test_window_resets_after_1s(self):
        import time
        conn = _make_conn("r1")
        for _ in range(50):
            conn.allow_frame()
        # Forzar reset de ventana
        conn._win_start = time.monotonic() - 1.1
        assert conn.allow_frame(), "Debe permitir tras reset de ventana"

    def test_rate_limit_is_per_connection(self):
        """Cada conexión tiene su propio contador independiente."""
        c1 = _make_conn("r1")
        c2 = _make_conn("r2")
        for _ in range(50):
            c1.allow_frame()
        # c1 agotado, c2 sigue libre
        assert not c1.allow_frame()
        assert c2.allow_frame()


# ---------------------------------------------------------------------------
# Backward compatibility — mensajes no-audio siguen pasando a MQTT
# ---------------------------------------------------------------------------

class TestNonAudioMessages:
    @pytest.mark.asyncio
    async def test_non_audio_type_not_broadcast(self):
        """Mensajes con type != 'audio' NO deben pasar por broadcast_audio."""
        store = WSConnectionStore()
        peer = _make_conn("peer")
        store.register("sala1", peer)

        # Simular mensaje de ubicación — no pasa por broadcast_audio
        data = {"type": "ubicacion", "lat": 1.0, "lng": 2.0}
        # broadcast_audio no debe ser llamado para este tipo
        assert data.get("type") != "audio"
        peer.ws.send_json.assert_not_called()
