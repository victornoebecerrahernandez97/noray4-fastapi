"""
PTTStore — Estado PTT en memoria. Latencia O(1), sin MongoDB.

Reglas:
- Solo un rider puede hablar por canal a la vez.
- El speaker debe soltar el turno antes que otro pueda tomarlo.
- Los admins pueden forzar la liberación con force_release().
- cleanup_sala() elimina todo el estado al cerrar una sala.

Thread-safety: todo acceso ocurre en el event loop asyncio (single-thread).
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from ms_voice.schemas import PTTState

logger = logging.getLogger("noray4.ptt")


class PTTConflictError(Exception):
    """Se lanza cuando otro rider ya tiene el turno en el canal."""
    def __init__(self, current_speaker_id: str, current_speaker_name: str) -> None:
        self.current_speaker_id = current_speaker_id
        self.current_speaker_name = current_speaker_name
        super().__init__(f"Canal ocupado por {current_speaker_name}")


class PTTStore:
    def __init__(self) -> None:
        # canal_id → PTTState actual
        self._states: Dict[str, PTTState] = {}
        # canal_id → set de rider_ids que han hablado esta sesión
        self._participants: Dict[str, Set[str]] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def set_speaking(
        self,
        canal_id: str,
        sala_id: str,
        rider_id: str,
        display_name: str,
    ) -> PTTState:
        """Toma el turno PTT. Lanza PTTConflictError si otro rider está hablando."""
        current = self._states.get(canal_id)
        if current and current.is_speaking and current.speaker_id != rider_id:
            raise PTTConflictError(current.speaker_id, current.speaker_name or "")

        state = PTTState(
            canal_id=canal_id,
            sala_id=sala_id,
            speaker_id=rider_id,
            speaker_name=display_name,
            is_speaking=True,
            timestamp=datetime.utcnow(),
        )
        self._states[canal_id] = state
        self._participants.setdefault(canal_id, set()).add(rider_id)
        logger.debug("PTT start — canal=%s rider=%s", canal_id, rider_id)
        return state

    def release_speaking(
        self,
        canal_id: str,
        sala_id: str,
        rider_id: str,
    ) -> PTTState:
        """Suelta el turno PTT. Idempotente si el rider no era el speaker."""
        current = self._states.get(canal_id)

        if not current or not current.is_speaking or current.speaker_id != rider_id:
            # Idempotente — retornar estado "sin speaker"
            return PTTState(
                canal_id=canal_id,
                sala_id=sala_id,
                is_speaking=False,
                timestamp=datetime.utcnow(),
            )

        state = PTTState(
            canal_id=canal_id,
            sala_id=sala_id,
            speaker_id=None,
            speaker_name=None,
            is_speaking=False,
            timestamp=datetime.utcnow(),
        )
        self._states[canal_id] = state
        logger.debug("PTT stop — canal=%s rider=%s", canal_id, rider_id)
        return state

    def force_release(self, canal_id: str) -> None:
        """Admin: fuerza liberación del turno sin importar quién habla."""
        current = self._states.get(canal_id)
        if current:
            self._states[canal_id] = PTTState(
                canal_id=canal_id,
                sala_id=current.sala_id,
                is_speaking=False,
                timestamp=datetime.utcnow(),
            )
            logger.info("PTT force-release — canal=%s", canal_id)

    def cleanup_sala(self, sala_id: str) -> None:
        """Elimina todo el estado de voz de la sala al cerrarla."""
        canales = [cid for cid, s in self._states.items() if s.sala_id == sala_id]
        for cid in canales:
            self._states.pop(cid, None)
            self._participants.pop(cid, None)
        if canales:
            logger.info("PTTStore: sala %s limpiada — %d canales", sala_id, len(canales))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_state(self, canal_id: str) -> Optional[PTTState]:
        return self._states.get(canal_id)

    def get_all_states(self, sala_id: str) -> List[PTTState]:
        return [s for s in self._states.values() if s.sala_id == sala_id]

    def get_participants(self, canal_id: str) -> List[str]:
        return list(self._participants.get(canal_id, set()))


# Singleton
ptt_store = PTTStore()
