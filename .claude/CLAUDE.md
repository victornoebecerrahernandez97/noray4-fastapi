# Noray4 API — Claude Brain

## Stack
- **Runtime:** FastAPI + Python 3.11+
- **Database:** MongoDB Atlas M0 (Motor async driver)
- **Deploy:** Railway (nixpacks builder) — 1 servicio monolítico
- **Messaging:** HiveMQ Cloud (MQTT over TLS) + WebSocket bridge
- **Auth:** JWT (python-jose) + Firebase (verificación Google tokens)
- **Storage:** Cloudinary

## Arquitectura: Monolítica modular

Un solo proceso FastAPI. Los módulos internos son `ms_{nombre}/` — no son procesos separados.

```
noray4-fastapi/
├── main.py              ← Entry point único: lifespan, CORS, routers, /health
├── shared/              ← Código compartido
│   ├── database.py      ← Singleton Motor/MongoDB + collection accessors
│   ├── auth.py          ← JWT verification
│   ├── dependencies.py  ← get_current_user, get_current_rider (FastAPI Depends)
│   ├── config.py        ← Pydantic BaseSettings desde .env
│   ├── models.py        ← NorayBase (Pydantic base model)
│   └── exceptions.py    ← HTTP exception handlers
├── ms_auth/             ← router.py, schemas.py, service.py, models.py
├── ms_riders/
├── ms_salas/
├── ms_realtime/         ← mqtt_client.py, ws_bridge.py
├── ms_chat/
├── ms_location/
├── ms_voice/
├── ms_amarres/
├── ms_groups/
├── railway.toml
├── Procfile
├── requirements.txt
└── .env.example
```

## Convenciones
- Carpetas de módulo: `ms_{nombre}` (snake_case)
- Cada módulo tiene: `router.py`, `schemas.py`, `service.py`, `models.py`, `__init__.py`
- Importar shared directamente: `from shared.database import get_database`
- Variables de entorno: **nunca hardcodear** — siempre via `config.py` / `Settings`
- Errores siempre con `HTTPException` y status codes correctos
- IDs MongoDB: serializar como `str`, nunca exponer `ObjectId` raw

## Patrón de router

```python
# ms_{nombre}/router.py
router = APIRouter(prefix="/{nombre}", tags=["{nombre}"])

# main.py — todos los routers se incluyen con PREFIX = "/api/v1"
app.include_router(nombre_router, prefix=PREFIX)
# Resultado: /api/v1/{nombre}/...
```

## Sprints
- **Sprint 1 (actual):** ms_auth, ms_riders, ms_salas, ms_realtime
- **Sprint 2:** ms_location, ms_voice, ms_amarres
- **Sprint 3:** ms_groups, ms_feed, ms_notifications

## Reglas
- SIEMPRE async/await — nunca operaciones síncronas con MongoDB
- Pydantic v2: usar `model_config = ConfigDict(...)`, no `class Config`
- Health check en `GET /health` → `{"status": "ok", "version": "...", "mqtt": bool}`
- CORS abierto en MVP: `allow_origins=["*"]`
- Al agregar un módulo nuevo: crear `ms_{nombre}/`, agregar router en `main.py`
- Máximo 150 líneas por archivo de servicio/router
