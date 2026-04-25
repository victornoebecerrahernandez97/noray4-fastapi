import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared.database import close_db, connect_db
from shared.exceptions import http_exception_handler, unhandled_exception_handler
from ms_auth.router import router as auth_router
from ms_riders.router import router as riders_router
from ms_salas.router import router as salas_router
from ms_chat.router import router as chat_router
from ms_realtime.router import router as realtime_router
from ms_realtime import mqtt_client, ws_bridge
from ms_chat.service import ensure_chat_indexes
from ms_location.router import router as location_router
from ms_location.service import ensure_location_indexes
from ms_voice.router import router as voice_router
from ms_voice.service import ensure_voice_indexes
from ms_amarres.router import router as amarres_router
from ms_amarres.service import ensure_amarre_indexes
from ms_groups.router import router as groups_router
from ms_groups.service import ensure_group_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await ensure_chat_indexes()
    await ensure_location_indexes()
    await ensure_voice_indexes()
    await ensure_amarre_indexes()
    await ensure_group_indexes()
    await mqtt_client.mqtt_gateway.connect()
    yield
    await mqtt_client.mqtt_gateway.disconnect()
    await close_db()


app = FastAPI(
    title="Noray4 API",
    version="0.2.0",
    description="""
## Noray4 — Backend API

Plataforma de comunidad rider con comunicación en tiempo real.

### Módulos disponibles
- **Auth** — Registro, login y gestión de sesiones JWT
- **Riders** — Perfiles, motos y red social entre riders
- **Salas** — Salas de ruta con acceso por QR y gestión de miembros
- **Realtime** — Gateway MQTT para ubicación, chat y presencia en tiempo real
- **Location** — POIs geoespaciales y tracks GPS en tiempo real
- **Voice** — Señalización PTT y WebRTC para voz en sala
- **Amarres** — Memoria de viajes: historial, fotos, GPX y feed social
- **Groups** — Grupos permanentes y comunidades rider

### Autenticación
Todos los endpoints protegidos requieren header:
`Authorization: Bearer <token>`

### WebSocket
Conectar al bridge en tiempo real:
`ws://<host>/ws/{sala_id}?token=<jwt>`

### Versión
Sprint 1 — MVP funcional. Voz disponible en Sprint 2.
    """,
    contact={
        "name": "Noray4",
        "url": "https://noray4.app",
    },
    license_info={
        "name": "Privado — uso interno",
    },
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

PREFIX = "/api/v1"

app.include_router(auth_router, prefix=PREFIX)
app.include_router(riders_router, prefix=PREFIX)
app.include_router(salas_router, prefix=PREFIX)
app.include_router(chat_router, prefix=PREFIX)
app.include_router(realtime_router, prefix=PREFIX)
app.include_router(location_router, prefix=PREFIX)
app.include_router(voice_router, prefix=PREFIX)
app.include_router(amarres_router, prefix=PREFIX)
app.include_router(groups_router, prefix=PREFIX)

# WebSocket bridge — Angular no puede conectar directo a MQTT, usa este endpoint
app.add_api_websocket_route("/ws/{sala_id}", ws_bridge.endpoint)


@app.get("/health", tags=["health"])
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mqtt": mqtt_client.mqtt_gateway.is_connected,
    }
