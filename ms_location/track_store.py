"""
TrackStore — Store en memoria para tracks activos durante una sala.

Diseño:
- Un dict anidado: tracks[sala_id][rider_id] = deque(maxlen=10_000)
- collections.deque actúa como ring buffer: al llegar al límite descarta el punto
  más antiguo automáticamente, sin overhead de memoria adicional.
- No requiere lock explícito: todo acceso ocurre en el event loop asyncio (single-thread).
- Al cerrar una sala (close_sala) se limpia la entrada del dict → GC libera memoria.
"""
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List

from ms_location.schemas import CoordUpdate, GPXExport, TrackOut

logger = logging.getLogger("noray4.track_store")

_MAX_POINTS = 10_000  # ring buffer size por rider por sala


class TrackStore:
    def __init__(self) -> None:
        # tracks[sala_id][rider_id] = deque of CoordUpdate
        self._tracks: Dict[str, Dict[str, deque]] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_point(self, sala_id: str, rider_id: str, point: CoordUpdate) -> None:
        """Agrega un punto al track del rider. Ring buffer de 10 000 puntos."""
        sala_tracks = self._tracks.setdefault(sala_id, {})
        if rider_id not in sala_tracks:
            sala_tracks[rider_id] = deque(maxlen=_MAX_POINTS)
        sala_tracks[rider_id].append(point)

    def clear_sala(self, sala_id: str) -> None:
        """Limpia todos los tracks de una sala al cerrarla. Libera memoria."""
        removed = self._tracks.pop(sala_id, None)
        if removed is not None:
            riders = len(removed)
            total = sum(len(d) for d in removed.values())
            logger.info(
                "TrackStore: sala %s limpiada — %d riders, %d puntos liberados",
                sala_id, riders, total,
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_track(self, sala_id: str, rider_id: str) -> List[CoordUpdate]:
        """Retorna los puntos de un rider en la sala (cronológico, más antiguo primero)."""
        sala_tracks = self._tracks.get(sala_id, {})
        return list(sala_tracks.get(rider_id, []))

    def get_all_tracks(self, sala_id: str) -> Dict[str, List[CoordUpdate]]:
        """Retorna todos los tracks de la sala como dict rider_id → List[CoordUpdate]."""
        sala_tracks = self._tracks.get(sala_id, {})
        return {rider_id: list(dq) for rider_id, dq in sala_tracks.items()}

    def get_active_riders(self, sala_id: str) -> List[str]:
        """Retorna rider_ids con al menos un punto registrado en la sala."""
        return list(self._tracks.get(sala_id, {}).keys())

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_gpx(self, sala_id: str) -> GPXExport:
        """
        Construye la estructura GPXExport lista para persistir en MS-Amarres.
        El nombre GPX es semántico — el formato de serialización real es JSON.
        Sprint 2 convertirá esto a XML GPX real si se requiere.
        """
        all_tracks = self.get_all_tracks(sala_id)
        riders = [
            TrackOut(rider_id=rider_id, points=points)
            for rider_id, points in all_tracks.items()
            if points  # omitir riders sin puntos
        ]
        return GPXExport(
            sala_id=sala_id,
            riders=riders,
            exported_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Métricas (útiles para debug / monitoring)
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "salas_activas": len(self._tracks),
            "detalle": {
                sala_id: {
                    rider_id: len(dq)
                    for rider_id, dq in riders.items()
                }
                for sala_id, riders in self._tracks.items()
            },
        }


# Singleton — importado por service.py y por el hook de cierre de sala
track_store = TrackStore()
