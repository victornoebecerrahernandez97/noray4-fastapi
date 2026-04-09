import logging
import re

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from shared.config import settings

logger = logging.getLogger("noray4.db")

_client: AsyncIOMotorClient | None = None


def _safe_uri(uri: str) -> str:
    """Returns the URI with the password replaced by *** for logging."""
    return re.sub(r"(?<=:)[^:@]+(?=@)", "***", uri)


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,  # fail fast instead of hanging 30s
    )
    # Motor is lazy — force a real network round-trip to validate credentials now.
    try:
        await _client.admin.command("ping")
        logger.info("MongoDB conectado: %s", _safe_uri(settings.MONGODB_URI))
    except Exception as exc:
        _client = None
        logger.error(
            "MongoDB FALLO al conectar (%s): %s",
            _safe_uri(settings.MONGODB_URI),
            exc,
        )
        raise RuntimeError(f"No se pudo conectar a MongoDB: {exc}") from exc


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB desconectado.")


def get_database() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _client["noray4"]


# Collection accessors
def get_users_collection():
    return get_database()["users"]


def get_riders_collection():
    return get_database()["riders"]


def get_salas_collection():
    return get_database()["salas"]


def get_mensajes_collection():
    return get_database()["mensajes"]


def get_amarres_collection():
    return get_database()["amarres"]  # usado por ms_amarres


def get_grupos_collection():
    return get_database()["grupos"]  # usado por ms_groups


def get_pois_collection():
    return get_database()["pois"]


def get_canales_collection():
    return get_database()["canales_voz"]
