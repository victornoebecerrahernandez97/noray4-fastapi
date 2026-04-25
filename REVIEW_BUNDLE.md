# REVIEW_BUNDLE — noray4-fastapi

Bundle generado para revisión externa. Contiene el código fuente literal de los módulos principales.

---

## Árbol del proyecto (hasta 3 niveles, excluye __pycache__, .venv, .git)

```
noray4-fastapi/
├── main.py
├── requirements.txt
├── Procfile
├── railway.toml
├── .env.example
├── .gitignore
├── DIAGNOSTIC.md
├── README.md
├── shared/
│   ├── __init__.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── exceptions.py
│   └── models.py
├── ms_auth/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── ms_riders/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── ms_salas/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── ms_realtime/
│   ├── __init__.py
│   ├── mqtt_client.py
│   ├── router.py
│   ├── schemas.py
│   └── ws_bridge.py
├── ms_location/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   └── track_store.py
├── ms_voice/
│   ├── __init__.py
│   ├── models.py
│   ├── ptt_store.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── ms_amarres/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── ms_chat/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
├── ms_groups/
│   ├── __init__.py
│   ├── models.py
│   ├── router.py
│   ├── schemas.py
│   └── service.py
└── tests/
    └── test_audio_relay.py
```

---

## Bloque 1 — Configuración del proyecto

### `requirements.txt` — 11 líneas

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
motor==3.6.0
pydantic-settings==2.6.1
pydantic[email]==2.10.3
python-jose[cryptography]==3.3.0
bcrypt==4.0.1
python-multipart==0.0.20
cloudinary==1.41.0
paho-mqtt==2.1.0
httpx==0.28.0
```

---

### `.env.example` — 20 líneas

```
# IMPORTANTE: si el password contiene caracteres especiales (@, #, $, /, ?, :, &, =, +, %)
# deben estar URL-encoded. Ejemplo: p@ss#1 → p%40ss%231
# Generador: python -c "import urllib.parse; print(urllib.parse.quote('tu_password', safe=''))"
MONGODB_URI=
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

HIVEMQ_HOST=xxxx.hivemq.cloud
HIVEMQ_PORT=8883
HIVEMQ_USER=
HIVEMQ_PASSWORD=
WS_MQTT_PORT=8884

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

FIREBASE_PROJECT_ID=noray4
ENVIRONMENT=development
```

---

### `railway.toml` — 7 líneas

```toml
[build]
builder = "nixpacks"

[[services]]
name = "noray4-api"
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
```

---

### `Procfile` — 1 línea

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

### `main.py` — 119 líneas

```python
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
    version="0.1.0",
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
```

---

## Bloque 2 — Shared (infraestructura)

### `shared/config.py` — 27 líneas

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MONGODB_URI: str = "mongodb://localhost:27017"
    JWT_SECRET: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    HIVEMQ_HOST: str = ""
    HIVEMQ_PORT: int = 8883
    HIVEMQ_USER: str = ""
    HIVEMQ_PASSWORD: str = ""
    WS_MQTT_PORT: int = 8884  # Puerto WebSocket MQTT de HiveMQ (para clientes directos)

    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    FIREBASE_PROJECT_ID: str = "noray4"
    ENVIRONMENT: str = "development"


settings = Settings()
```

---

### `shared/database.py` — 82 líneas

```python
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
```

---

### `shared/auth.py` — 37 líneas

```python
import bcrypt
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt

from shared.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

---

### `shared/dependencies.py` — 37 líneas

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import verify_token
from shared.database import get_riders_collection, get_users_collection

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Returns the user_id (str) extracted from the Bearer JWT."""
    payload = verify_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sujeto válido",
        )
    return user_id


async def get_current_rider(
    user_id: str = Depends(get_current_user),
) -> dict:
    """Returns the full Rider document for the authenticated user."""
    collection = get_riders_collection()
    rider = await collection.find_one({"user_id": user_id})
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de rider no encontrado",
        )
    rider["_id"] = str(rider["_id"])
    return rider
```

---

### `shared/models.py` — 6 líneas

Nota: casi vacío — actúa solo como base Pydantic compartida.

```python
from pydantic import BaseModel, ConfigDict


class NorayBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
```

---

### `shared/exceptions.py` — 18 líneas

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"},
    )
```

---

## Bloque 3 — Auth (módulo crítico)

### `ms_auth/router.py` — 92 líneas

```python
import logging

from fastapi import APIRouter, Depends, status

from shared.dependencies import get_current_user
from ms_auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ms_auth import service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("noray4.auth")


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description=(
        "Crea una cuenta nueva con email y contraseña. Genera automáticamente el perfil de rider "
        "asociado. Retorna un JWT de acceso. Lanza 409 si el email ya está registrado."
    ),
)
async def register(body: RegisterRequest):
    logger.info("REGISTER attempt: email=%s, display_name=%s", body.email, body.display_name)
    logger.info(
        "REGISTER body: email=%s, display_name=%s, password_len=%d, password_preview=%s",
        body.email,
        body.display_name,
        len(body.password),
        "*" * len(body.password),
    )
    return await service.register_user(body.email, body.password, body.display_name)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Autentica al usuario con email y contraseña. Retorna un JWT Bearer válido por el tiempo "
        "configurado en JWT_EXPIRE_MINUTES. Lanza 401 si las credenciales son incorrectas."
    ),
)
async def login(body: LoginRequest):
    logger.info("LOGIN attempt: email=%s", body.email)
    return await service.login_user(body.email, body.password)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Cerrar sesión",
    description=(
        "Invalida la sesión del usuario. En esta versión el JWT es stateless; el logout es semántico. "
        "En Sprint 2 se implementará blocklist de tokens."
    ),
)
async def logout(user_id: str = Depends(get_current_user)):
    logger.info("LOGOUT: user_id=%s", user_id)
    # JWT is stateless; invalidation would require a blocklist — acknowledged for Sprint 2.
    return {"status": "ok", "detail": "Sesión cerrada"}


@router.get(
    "/me",
    response_model=UserOut,
    summary="Obtener usuario autenticado",
    description=(
        "Retorna los datos del usuario actualmente autenticado a partir del JWT en el header "
        "Authorization. Lanza 401 si el token es inválido o ha expirado."
    ),
)
async def me(user_id: str = Depends(get_current_user)):
    logger.info("ME: user_id=%s", user_id)
    user = await service.get_user_by_id(user_id)
    return user


@router.post(
    "/guest-token",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar token de invitado",
    description=(
        "Genera un JWT temporal con TTL de 24 horas y flag is_guest=true. Permite acceso a salas "
        "públicas vía QR sin necesidad de cuenta registrada."
    ),
)
async def guest_token():
    logger.info("GUEST_TOKEN: new guest token requested")
    return await service.create_guest_token()
```

---

### `ms_auth/schemas.py` — 28 líneas

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    email: EmailStr
    display_name: str
    is_guest: bool
    is_active: bool
```

---

### `ms_auth/service.py` — 115 líneas

```python
import logging
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException, status

from shared.auth import create_access_token, hash_password, verify_password
from shared.database import get_users_collection

logger = logging.getLogger("noray4.auth")


async def register_user(email: str, password: str, display_name: str) -> dict:
    collection = get_users_collection()

    existing = await collection.find_one({"email": email})
    if existing:
        logger.info("REGISTER conflict: email=%s already exists", email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese correo",
        )

    logger.info("hash_password for: %s", email)
    now = datetime.utcnow()
    doc = {
        "email": email,
        "hashed_password": hash_password(password),
        "display_name": display_name,
        "is_guest": False,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    logger.info("DB insert user: %s", email)
    result = await collection.insert_one(doc)
    user_id = str(result.inserted_id)

    # Auto-create rider profile — import here to avoid circular imports at module load
    try:
        from ms_riders.service import create_rider
        await create_rider(user_id, {"display_name": display_name})
    except HTTPException as exc:
        # 409 means the rider already exists — safe to ignore
        if exc.status_code != status.HTTP_409_CONFLICT:
            logger.warning("No se pudo crear el perfil de rider para %s: %s", user_id, exc.detail)
    except Exception as exc:
        logger.warning("Error inesperado al crear rider para %s: %s", user_id, exc)

    logger.info("REGISTER success: email=%s, user_id=%s", email, user_id)
    token = create_access_token({"sub": user_id})
    return {"access_token": token, "token_type": "bearer"}


async def login_user(email: str, password: str) -> dict:
    collection = get_users_collection()

    user = await collection.find_one({"email": email, "is_guest": False})
    if not user or not verify_password(password, user.get("hashed_password", "")):
        logger.error("LOGIN failed: invalid credentials for email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    if not user.get("is_active", True):
        logger.error("LOGIN failed: account disabled for email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )

    user_id = str(user["_id"])
    logger.info("LOGIN success: email=%s, user_id=%s", email, user_id)
    token = create_access_token({"sub": user_id})
    return {"access_token": token, "token_type": "bearer"}


async def get_user_by_id(user_id: str) -> dict:
    collection = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido")

    user = await collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    user["_id"] = str(user["_id"])
    return user


async def create_guest_token() -> dict:
    """Generates a 24-hour temporary token for QR/invite access."""
    logger.info("GUEST_TOKEN: creating guest user")
    collection = get_users_collection()

    now = datetime.utcnow()
    doc = {
        "email": f"guest_{ObjectId()}@noray4.guest",
        "hashed_password": None,
        "display_name": "Invitado",
        "is_guest": True,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    logger.info("DB insert user: guest")
    result = await collection.insert_one(doc)
    user_id = str(result.inserted_id)

    logger.info("GUEST_TOKEN success: user_id=%s", user_id)
    token = create_access_token({"sub": user_id}, expires_delta=timedelta(hours=24))
    return {"access_token": token, "token_type": "bearer"}
```

---

### `ms_auth/models.py` — 18 líneas

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    email: EmailStr
    hashed_password: Optional[str] = None  # None for OAuth/guest users
    display_name: str
    is_guest: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Bloque 4 — Salas (módulo con gap de integración)

### `ms_salas/router.py` — 135 líneas

```python
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from shared.dependencies import get_current_rider
from ms_salas.schemas import JoinRequest, MiembroOut, QROut, SalaCreate, SalaOut, SalaUpdate
from ms_salas import service

router = APIRouter(prefix="/salas", tags=["salas"])


@router.get(
    "",
    response_model=list[SalaOut],
    summary="Listar salas activas",
    description=(
        "Retorna la lista paginada de salas con status active, ordenadas por fecha de creación "
        "descendente. Soporta parámetros skip y limit para paginación."
    ),
)
async def list_salas(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_salas_activas(skip=skip, limit=limit)


@router.post(
    "",
    response_model=SalaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva sala",
    description=(
        "Crea una sala de ruta con nombre, descripción y privacidad configurables. El rider autenticado "
        "se convierte automáticamente en administrador. Genera QR token y link de invitación."
    ),
)
async def create_sala(body: SalaCreate, rider: dict = Depends(get_current_rider)):
    return await service.create_sala(
        owner_rider_id=rider["_id"],
        owner_display_name=rider["display_name"],
        data=body,
    )


@router.get(
    "/{sala_id}",
    response_model=SalaOut,
    summary="Obtener detalle de sala",
    description=(
        "Retorna todos los datos de una sala incluyendo lista de miembros, estado y metadatos. "
        "Lanza 404 si la sala no existe."
    ),
)
async def get_sala(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_sala_by_id(sala_id)


@router.put(
    "/{sala_id}",
    response_model=SalaOut,
    summary="Actualizar sala",
    description=(
        "Actualiza nombre, descripción o privacidad de la sala. Solo el miembro con rol admin puede "
        "realizar esta operación. Lanza 403 si el rider autenticado no es administrador."
    ),
)
async def update_sala(
    sala_id: str,
    body: SalaUpdate,
    rider: dict = Depends(get_current_rider),
):
    return await service.update_sala(sala_id, rider["_id"], body)


@router.post(
    "/{sala_id}/join",
    response_model=SalaOut,
    summary="Unirse a una sala",
    description=(
        "Agrega al rider autenticado como miembro con rol rider. Para salas privadas requiere "
        "qr_token válido en el body. Operación idempotente: si ya es miembro retorna la sala sin error."
    ),
)
async def join_sala(
    sala_id: str,
    body: Optional[JoinRequest] = Body(default=None),
    rider: dict = Depends(get_current_rider),
):
    return await service.join_sala(
        sala_id=sala_id,
        rider_id=rider["_id"],
        display_name=rider["display_name"],
        qr_token=body.qr_token if body else None,
    )


@router.post(
    "/{sala_id}/close",
    response_model=SalaOut,
    summary="Cerrar sala",
    description=(
        "Cambia el status de la sala a closed y registra la fecha de cierre. Solo el administrador "
        "puede cerrar la sala. En Sprint 2 disparará la creación automática del amarre."
    ),
)
async def close_sala(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.close_sala(sala_id, rider["_id"])


@router.get(
    "/{sala_id}/qr",
    response_model=QROut,
    summary="Obtener QR de invitación",
    description=(
        "Retorna el token QR y el link de invitación de la sala. Solo accesible para miembros "
        "actuales. Lanza 403 si el rider autenticado no pertenece a la sala."
    ),
)
async def get_qr(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_qr(sala_id, rider["_id"])


@router.get(
    "/{sala_id}/miembros",
    response_model=list[MiembroOut],
    summary="Listar miembros de la sala",
    description=(
        "Retorna la lista completa de miembros de la sala con su rol y fecha de ingreso."
    ),
)
async def get_miembros(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_miembros(sala_id)
```

---

### `ms_salas/schemas.py` — 47 líneas

```python
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SalaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    is_private: bool = False


class SalaUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    is_private: Optional[bool] = None


class JoinRequest(BaseModel):
    qr_token: Optional[str] = None


class MiembroOut(BaseModel):
    rider_id: str
    display_name: str
    role: Literal["admin", "rider", "guest"]
    joined_at: datetime


class SalaOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str
    status: Literal["active", "closed"]
    is_private: bool
    miembros: List[MiembroOut]
    qr_token: Optional[str] = None
    invite_link: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None


class QROut(BaseModel):
    qr_token: str
    invite_link: str
```

---

### `ms_salas/service.py` — 224 líneas

```python
import logging
import secrets
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from shared.database import get_salas_collection
from ms_salas.schemas import SalaCreate, SalaUpdate

logger = logging.getLogger("noray4.salas")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oid(sala_id: str) -> ObjectId:
    try:
        return ObjectId(sala_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de sala inválido")


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _require_sala(sala_id: str) -> dict:
    collection = get_salas_collection()
    sala = await collection.find_one({"_id": _oid(sala_id)})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salida no encontrada")
    return _serialize(sala)


def _require_admin(sala: dict, rider_id: str) -> None:
    if sala["owner_id"] != rider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el admin puede realizar esta acción",
        )


def _is_member(sala: dict, rider_id: str) -> bool:
    return any(m["rider_id"] == rider_id for m in sala.get("miembros", []))


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def create_sala(owner_rider_id: str, owner_display_name: str, data: SalaCreate) -> dict:
    collection = get_salas_collection()

    qr_token = secrets.token_urlsafe(16)
    now = datetime.utcnow()

    doc = {
        "name": data.name,
        "description": data.description,
        "owner_id": owner_rider_id,
        "status": "active",
        "is_private": data.is_private,
        "miembros": [
            {
                "rider_id": owner_rider_id,
                "display_name": owner_display_name,
                "role": "admin",
                "joined_at": now,
            }
        ],
        "qr_token": qr_token,
        "invite_link": None,  # filled after insert_one so we have the sala_id
        "created_at": now,
        "closed_at": None,
    }

    result = await collection.insert_one(doc)
    sala_id = str(result.inserted_id)
    invite_link = f"https://noray4.app/sala/{sala_id}?token={qr_token}"

    await collection.update_one(
        {"_id": result.inserted_id},
        {"$set": {"invite_link": invite_link}},
    )

    doc["_id"] = sala_id
    doc["invite_link"] = invite_link

    # Crear canales de voz default — import local para evitar circular imports
    try:
        from ms_voice.service import create_default_canales
        await create_default_canales(sala_id, owner_rider_id)
    except Exception as exc:
        logger.warning("No se pudieron crear canales de voz para sala %s: %s", sala_id, exc)

    return doc


async def get_salas_activas(skip: int = 0, limit: int = 20) -> List[dict]:
    collection = get_salas_collection()
    cursor = (
        collection.find({"status": "active"})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    salas = []
    async for doc in cursor:
        salas.append(_serialize(doc))
    return salas


async def get_sala_by_id(sala_id: str) -> dict:
    return await _require_sala(sala_id)


async def update_sala(sala_id: str, rider_id: str, data: SalaUpdate) -> dict:
    sala = await _require_sala(sala_id)
    _require_admin(sala, rider_id)

    patch = data.model_dump(exclude_none=True)
    if not patch:
        return sala

    collection = get_salas_collection()
    result = await collection.find_one_and_update(
        {"_id": _oid(sala_id)},
        {"$set": patch},
        return_document=True,
    )
    return _serialize(result)


async def join_sala(
    sala_id: str,
    rider_id: str,
    display_name: str,
    qr_token: Optional[str] = None,
) -> dict:
    sala = await _require_sala(sala_id)

    if sala["status"] == "closed":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="La salida está cerrada")

    if sala["is_private"]:
        if not qr_token or qr_token != sala.get("qr_token"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token de invitación inválido o requerido",
            )

    # Idempotent: already a member → return sala as-is
    if _is_member(sala, rider_id):
        return sala

    new_member = {
        "rider_id": rider_id,
        "display_name": display_name,
        "role": "rider",
        "joined_at": datetime.utcnow(),
    }

    collection = get_salas_collection()
    result = await collection.find_one_and_update(
        {"_id": _oid(sala_id)},
        {"$push": {"miembros": new_member}},
        return_document=True,
    )
    return _serialize(result)


async def close_sala(sala_id: str, rider_id: str) -> dict:
    sala = await _require_sala(sala_id)
    _require_admin(sala, rider_id)

    if sala["status"] == "closed":
        return sala

    collection = get_salas_collection()
    result = await collection.find_one_and_update(
        {"_id": _oid(sala_id)},
        {"$set": {"status": "closed", "closed_at": datetime.utcnow()}},
        return_document=True,
    )
    closed_sala = _serialize(result)

    # Crear amarre automático — import local para evitar circular imports
    try:
        from ms_amarres.service import create_amarre_from_sala
        riders = [m["rider_id"] for m in closed_sala.get("miembros", [])]
        riders_display = [
            {"rider_id": m["rider_id"], "display_name": m["display_name"]}
            for m in closed_sala.get("miembros", [])
        ]
        amarre = await create_amarre_from_sala(sala_id, rider_id, riders, riders_display)
        return {"sala": closed_sala, "amarre": amarre}
    except Exception as exc:
        logger.warning("No se pudo crear amarre para sala %s: %s", sala_id, exc)
        return closed_sala


async def get_qr(sala_id: str, rider_id: str) -> dict:
    sala = await _require_sala(sala_id)

    if not _is_member(sala, rider_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes ser miembro de la salida para ver el QR",
        )

    return {
        "qr_token": sala["qr_token"],
        "invite_link": sala["invite_link"],
    }


async def get_miembros(sala_id: str) -> List[dict]:
    sala = await _require_sala(sala_id)
    return sala.get("miembros", [])
```

---

## Bloque 5 — Location (memoria volátil a migrar)

### `ms_location/router.py` — 155 líneas

```python
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from shared.dependencies import get_current_rider
from ms_location.schemas import CoordUpdate, GPXExport, POICreate, POIOut, POIUpdate
from ms_location import service

router = APIRouter(prefix="/location", tags=["location"])


# ---------------------------------------------------------------------------
# POIs
# ---------------------------------------------------------------------------

@router.post(
    "/pois",
    response_model=POIOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear punto de interés",
    description=(
        "Persiste un POI en MongoDB con índice geoespacial 2dsphere. "
        "Puede asociarse a una sala (sala_id) o ser global (public=True)."
    ),
)
async def create_poi(body: POICreate, rider: dict = Depends(get_current_rider)):
    return await service.create_poi(rider["_id"], rider["display_name"], body)


@router.get(
    "/pois",
    response_model=List[POIOut],
    summary="Listar POIs",
    description=(
        "Retorna POIs filtrados por categoría, sala o radio geográfico. "
        "Si se pasan lat/lng usa $near (requiere índice 2dsphere). Máx 200 resultados."
    ),
)
async def list_pois(
    lat: Optional[float] = Query(default=None, ge=-90, le=90),
    lng: Optional[float] = Query(default=None, ge=-180, le=180),
    radius_m: int = Query(default=5000, ge=100, le=50000),
    category: Optional[str] = Query(default=None),
    sala_id: Optional[str] = Query(default=None),
    public_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_pois(
        lat=lat, lng=lng, radius_m=radius_m,
        category=category, public_only=public_only,
        sala_id=sala_id, limit=limit,
    )


@router.get(
    "/pois/{poi_id}",
    response_model=POIOut,
    summary="Obtener POI por ID",
    description="Retorna un POI específico. Lanza 404 si no existe.",
)
async def get_poi(poi_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_poi_by_id(poi_id)


@router.put(
    "/pois/{poi_id}",
    response_model=POIOut,
    summary="Actualizar POI",
    description="Actualiza nombre, descripción, categoría o visibilidad. Solo el creador puede editar.",
)
async def update_poi(poi_id: str, body: POIUpdate, rider: dict = Depends(get_current_rider)):
    return await service.update_poi(poi_id, rider["_id"], body)


@router.delete(
    "/pois/{poi_id}",
    summary="Eliminar POI",
    description="Elimina físicamente el POI. Solo el creador puede borrar. Lanza 403 en caso contrario.",
)
async def delete_poi(poi_id: str, rider: dict = Depends(get_current_rider)):
    return await service.delete_poi(poi_id, rider["_id"])


@router.post(
    "/pois/{poi_id}/like",
    response_model=POIOut,
    summary="Toggle like en POI",
    description=(
        "Si el rider ya dio like lo quita; si no lo tenía lo agrega. "
        "Idempotente y seguro para doble tap."
    ),
)
async def toggle_like(poi_id: str, rider: dict = Depends(get_current_rider)):
    return await service.toggle_like(poi_id, rider["_id"])


# ---------------------------------------------------------------------------
# Tracks (in-memory)
# ---------------------------------------------------------------------------

@router.post(
    "/salas/{sala_id}/update",
    summary="Actualizar posición del rider",
    description=(
        "Registra la posición GPS actual del rider en la sala. Almacena el punto en el TrackStore "
        "en memoria y publica las coordenadas al topic MQTT de ubicación. Retorna la última posición "
        "conocida de todos los riders activos en la sala."
    ),
)
async def update_position(
    sala_id: str,
    body: CoordUpdate,
    rider: dict = Depends(get_current_rider),
):
    body = body.model_copy(update={"rider_id": rider["_id"]})
    return service.update_position(sala_id, body)


@router.get(
    "/salas/{sala_id}/tracks",
    summary="Obtener tracks activos de la sala",
    description=(
        "Retorna todos los puntos de track en memoria para cada rider activo. "
        "Datos efímeros — se pierden al reiniciar el servidor o al llamar /clear."
    ),
)
async def get_tracks(sala_id: str, rider: dict = Depends(get_current_rider)):
    return service.get_tracks(sala_id)


@router.get(
    "/salas/{sala_id}/export",
    response_model=GPXExport,
    summary="Exportar tracks como GPXExport",
    description=(
        "Genera la estructura GPXExport con todos los tracks de la sala. "
        "Lista para persistir en MS-Amarres al cierre. En Sprint 2 se añade serialización XML GPX."
    ),
)
async def export_gpx(sala_id: str, rider: dict = Depends(get_current_rider)):
    return service.export_gpx(sala_id)


@router.post(
    "/salas/{sala_id}/clear",
    summary="Limpiar tracks de la sala",
    description=(
        "Elimina todos los tracks en memoria de la sala. "
        "Llamado automáticamente por MS-Salas al cerrar una sala (Sprint 2)."
    ),
)
async def clear_tracks(sala_id: str, rider: dict = Depends(get_current_rider)):
    return service.clear_tracks(sala_id)
```

---

### `ms_location/service.py` — 225 líneas

```python
import logging
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING

from shared.database import get_pois_collection
from ms_location.schemas import CoordUpdate, GPXExport, POICreate, POIUpdate
from ms_location.track_store import track_store

logger = logging.getLogger("noray4.location")

_POI_PROJECTION = {
    "_id": 1, "sala_id": 1, "rider_id": 1, "display_name": 1,
    "category": 1, "name": 1, "description": 1,
    "lat": 1, "lng": 1, "public": 1, "likes": 1, "created_at": 1,
}


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_location_indexes() -> None:
    col = get_pois_collection()
    await col.create_index([("location", "2dsphere")], name="geo_2dsphere", background=True)
    await col.create_index([("sala_id", ASCENDING)], name="poi_sala_id", background=True)
    await col.create_index(
        [("public", ASCENDING), ("category", ASCENDING)],
        name="poi_public_category", background=True,
    )
    await col.create_index([("rider_id", ASCENDING)], name="poi_rider_id", background=True)
    logger.info("Índices de POIs verificados")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido")


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _get_poi(poi_id: str) -> dict:
    col = get_pois_collection()
    doc = await col.find_one({"_id": _oid(poi_id)}, _POI_PROJECTION)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI no encontrado")
    return _serialize(doc)


# ---------------------------------------------------------------------------
# POI — CRUD
# ---------------------------------------------------------------------------

async def create_poi(rider_id: str, display_name: str, data: POICreate) -> dict:
    col = get_pois_collection()
    doc = {
        "sala_id": data.sala_id,
        "rider_id": rider_id,
        "display_name": display_name,
        "category": data.category,
        "name": data.name,
        "description": data.description,
        "lat": data.lat,
        "lng": data.lng,
        "public": data.public,
        "likes": [],
        "created_at": datetime.utcnow(),
        # Campo GeoJSON para índice 2dsphere — no expuesto en POIOut
        "location": {"type": "Point", "coordinates": [data.lng, data.lat]},
    }
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return {k: v for k, v in doc.items() if k != "location"}


async def get_pois(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_m: int = 5000,
    category: Optional[str] = None,
    public_only: bool = True,
    sala_id: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    col = get_pois_collection()
    query: dict = {}

    if lat is not None and lng is not None:
        # Requiere índice 2dsphere
        query["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": radius_m,
            }
        }

    if public_only:
        query["public"] = True
    if category:
        query["category"] = category
    if sala_id:
        query["sala_id"] = sala_id

    cursor = col.find(query, _POI_PROJECTION).limit(min(limit, 200))
    return [_serialize(doc) async for doc in cursor]


async def get_poi_by_id(poi_id: str) -> dict:
    return await _get_poi(poi_id)


async def update_poi(poi_id: str, rider_id: str, data: POIUpdate) -> dict:
    poi = await _get_poi(poi_id)
    if poi["rider_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede editar este POI")

    patch = data.model_dump(exclude_none=True)
    if not patch:
        return poi

    col = get_pois_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(poi_id)},
        {"$set": patch},
        projection=_POI_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def delete_poi(poi_id: str, rider_id: str) -> dict:
    poi = await _get_poi(poi_id)
    if poi["rider_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede eliminar este POI")

    col = get_pois_collection()
    await col.delete_one({"_id": _oid(poi_id)})
    return {"status": "ok", "detail": "POI eliminado"}


async def toggle_like(poi_id: str, rider_id: str) -> dict:
    """Idempotente: si ya tiene like lo quita, si no lo agrega."""
    await _get_poi(poi_id)  # validates existence
    col = get_pois_collection()

    # Verificar si ya tiene like
    has_like = await col.find_one({"_id": _oid(poi_id), "likes": rider_id})
    op = "$pull" if has_like else "$addToSet"

    result = await col.find_one_and_update(
        {"_id": _oid(poi_id)},
        {op: {"likes": rider_id}},
        projection=_POI_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


# ---------------------------------------------------------------------------
# Track — delegado a TrackStore (in-memory)
# ---------------------------------------------------------------------------

def add_track_point(sala_id: str, point: CoordUpdate) -> None:
    track_store.add_point(sala_id, point.rider_id, point)


def update_position(sala_id: str, point: CoordUpdate) -> dict:
    """Almacena el punto en TrackStore y publica al topic MQTT. Retorna last_positions."""
    track_store.add_point(sala_id, point.rider_id, point)

    try:
        from ms_realtime.mqtt_client import mqtt_gateway
        mqtt_gateway.publish(
            f"noray4/{sala_id}/ubicacion",
            point.model_dump(mode="json"),
        )
    except Exception as exc:
        logger.debug("MQTT publish (ubicacion) ignorado: %s", exc)

    return {"status": "ok", "last_positions": _last_positions(sala_id)}


def _last_positions(sala_id: str) -> dict:
    """Última posición conocida de cada rider activo en la sala."""
    all_tracks = track_store.get_all_tracks(sala_id)
    result = {}
    for rider_id, points in all_tracks.items():
        if points:
            last = points[-1]
            result[rider_id] = last.model_dump(mode="json")
    return result


def get_tracks(sala_id: str) -> dict:
    all_tracks = track_store.get_all_tracks(sala_id)
    return {
        "sala_id": sala_id,
        "riders": [
            {"rider_id": rid, "points": [p.model_dump() for p in pts]}
            for rid, pts in all_tracks.items()
        ],
        "active_riders": len(all_tracks),
    }


def export_gpx(sala_id: str) -> GPXExport:
    return track_store.export_gpx(sala_id)


def clear_tracks(sala_id: str) -> dict:
    track_store.clear_sala(sala_id)
    return {"status": "ok", "detail": f"Tracks de sala {sala_id} limpiados"}
```

---

### `ms_location/track_store.py` — 109 líneas

```python
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
```

---

### `ms_location/schemas.py` — 73 líneas

```python
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Track (ephemeral, in-memory)
# ---------------------------------------------------------------------------

class CoordUpdate(BaseModel):
    rider_id: Optional[str] = None  # sobreescrito por el JWT en el endpoint; nunca del body
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    heading: Optional[float] = Field(default=None, ge=0, le=360)
    speed: Optional[float] = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrackOut(BaseModel):
    rider_id: str
    points: List[CoordUpdate]


class GPXExport(BaseModel):
    sala_id: str
    riders: List[TrackOut]
    exported_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# POI (persisted in MongoDB)
# ---------------------------------------------------------------------------

class POICreate(BaseModel):
    category: Literal[
        "gasolinera", "mecanico", "mirador",
        "comida", "hotel", "peligro", "otro",
    ]
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    public: bool = False
    sala_id: Optional[str] = None


class POIUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    category: Optional[Literal[
        "gasolinera", "mecanico", "mirador",
        "comida", "hotel", "peligro", "otro",
    ]] = None
    public: Optional[bool] = None


class POIOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    sala_id: Optional[str] = None
    rider_id: str
    display_name: str
    category: str
    name: str
    description: Optional[str] = None
    lat: float
    lng: float
    public: bool
    likes: List[str]
    created_at: datetime
```

---

## Bloque 6 — Realtime + Voice (bug de seguridad PTT)

### `ms_realtime/ws_bridge.py` — 219 líneas

```python
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
```

---

### `ms_realtime/mqtt_client.py` — 185 líneas

```python
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
```

---

### `ms_voice/ptt_store.py` — 132 líneas

```python
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
```

---

### `ms_voice/service.py` — 191 líneas

```python
import logging
from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING

from shared.database import get_canales_collection, get_salas_collection
from ms_voice.ptt_store import PTTConflictError, ptt_store
from ms_voice.schemas import CanalCreate, PTTRequest, PTTState, VozStatusOut, WebRTCSignal

logger = logging.getLogger("noray4.voice")

_CANAL_PROJECTION = {"_id": 1, "sala_id": 1, "name": 1, "activo": 1, "created_by": 1, "created_at": 1}
_DEFAULT_CANALES = ["general", "lideres", "emergencia"]


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_voice_indexes() -> None:
    col = get_canales_collection()
    await col.create_index([("sala_id", ASCENDING)], name="canal_sala_id", background=True)
    await col.create_index(
        [("sala_id", ASCENDING), ("activo", ASCENDING)],
        name="canal_sala_activo", background=True,
    )
    logger.info("Índices de canales de voz verificados")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _require_member(sala_id: str, rider_id: str) -> dict:
    try:
        oid = ObjectId(sala_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de sala inválido")
    salas = get_salas_collection()
    sala = await salas.find_one({"_id": oid})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")
    if not any(m["rider_id"] == rider_id for m in sala.get("miembros", [])):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta sala")
    sala["_id"] = str(sala["_id"])
    return sala


def _publish_voz(sala_id: str, payload: dict) -> None:
    """Fire-and-forget MQTT publish al topic de voz."""
    try:
        from ms_realtime.mqtt_client import mqtt_gateway
        mqtt_gateway.publish(f"noray4/{sala_id}/voz", payload)
    except Exception as exc:
        logger.debug("MQTT publish (voz) ignorado: %s", exc)


# ---------------------------------------------------------------------------
# Canales
# ---------------------------------------------------------------------------

async def create_canal(sala_id: str, rider_id: str, data: CanalCreate) -> dict:
    await _require_member(sala_id, rider_id)
    col = get_canales_collection()
    doc = {
        "sala_id": sala_id,
        "name": data.name,
        "created_by": rider_id,
        "activo": True,
        "created_at": datetime.utcnow(),
    }
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def create_default_canales(sala_id: str, rider_id: str) -> None:
    """Crea los 3 canales default al abrir una sala. Llamado desde ms_salas.create_sala."""
    col = get_canales_collection()
    now = datetime.utcnow()
    docs = [
        {"sala_id": sala_id, "name": name, "created_by": rider_id, "activo": True, "created_at": now}
        for name in _DEFAULT_CANALES
    ]
    await col.insert_many(docs)
    logger.info("Canales default creados para sala %s", sala_id)


async def get_canales(sala_id: str, rider_id: str) -> List[dict]:
    await _require_member(sala_id, rider_id)
    col = get_canales_collection()
    cursor = col.find({"sala_id": sala_id, "activo": True}, _CANAL_PROJECTION)
    return [_serialize(doc) async for doc in cursor]


# ---------------------------------------------------------------------------
# PTT
# ---------------------------------------------------------------------------

async def ptt_action(
    sala_id: str,
    rider_id: str,
    display_name: str,
    data: PTTRequest,
) -> PTTState:
    await _require_member(sala_id, rider_id)

    if data.action == "start":
        try:
            state = ptt_store.set_speaking(data.canal_id, sala_id, rider_id, display_name)
        except PTTConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Canal ocupado — {exc.current_speaker_name} está hablando",
            )
        _publish_voz(sala_id, {
            "type": "ptt_start",
            "canal_id": data.canal_id,
            "speaker_id": rider_id,
            "speaker_name": display_name,
            "timestamp": state.timestamp.isoformat(),
        })
    else:
        state = ptt_store.release_speaking(data.canal_id, sala_id, rider_id)
        _publish_voz(sala_id, {
            "type": "ptt_stop",
            "canal_id": data.canal_id,
            "speaker_id": rider_id,
            "timestamp": state.timestamp.isoformat(),
        })

    return state


async def get_voz_status(sala_id: str, rider_id: str) -> List[VozStatusOut]:
    await _require_member(sala_id, rider_id)
    col = get_canales_collection()
    cursor = col.find({"sala_id": sala_id, "activo": True}, _CANAL_PROJECTION)

    result = []
    async for canal in cursor:
        canal_id = str(canal["_id"])
        state = ptt_store.get_state(canal_id)
        result.append(VozStatusOut(
            canal_id=canal_id,
            canal_name=canal["name"],
            is_speaking=state.is_speaking if state else False,
            speaker_id=state.speaker_id if state else None,
            speaker_name=state.speaker_name if state else None,
            participants=ptt_store.get_participants(canal_id),
        ))
    return result


# ---------------------------------------------------------------------------
# WebRTC Signaling
# ---------------------------------------------------------------------------

async def send_signal(sala_id: str, rider_id: str, data: WebRTCSignal) -> dict:
    await _require_member(sala_id, rider_id)
    _publish_voz(sala_id, {
        "type": data.type,
        "from_rider_id": rider_id,
        "target_rider_id": data.target_rider_id,
        "canal_id": data.canal_id,
        "payload": data.payload,
    })
    return {"status": "sent"}


async def force_release(sala_id: str, rider_id: str, canal_id: str) -> dict:
    sala = await _require_member(sala_id, rider_id)
    if sala["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el admin puede forzar liberación")
    ptt_store.force_release(canal_id)
    _publish_voz(sala_id, {
        "type": "ptt_force_release",
        "canal_id": canal_id,
        "by_rider_id": rider_id,
        "timestamp": datetime.utcnow().isoformat(),
    })
    return {"status": "released", "canal_id": canal_id}
```

---

## Bloque 7 — Riders (stats placeholder)

### `ms_riders/router.py` — 99 líneas

```python
from fastapi import APIRouter, Depends, status

from shared.dependencies import get_current_user
from ms_riders.schemas import MotoUpdate, RiderOut, RiderUpdate, StatsOut
from ms_riders import service

router = APIRouter(prefix="/riders", tags=["riders"])


@router.get(
    "/me",
    response_model=RiderOut,
    summary="Obtener mi perfil de rider",
    description=(
        "Retorna el perfil completo del rider autenticado incluyendo datos de moto, estadísticas y "
        "contadores de seguidores. Lanza 404 si el perfil aún no ha sido creado."
    ),
)
async def get_my_rider(user_id: str = Depends(get_current_user)):
    return await service.get_rider_by_user_id(user_id)


@router.put(
    "/me",
    response_model=RiderOut,
    summary="Actualizar mi perfil",
    description=(
        "Actualiza los campos del perfil del rider autenticado. Todos los campos son opcionales. "
        "Retorna el perfil actualizado. No permite modificar user_id ni timestamps."
    ),
)
async def update_my_rider(body: RiderUpdate, user_id: str = Depends(get_current_user)):
    return await service.update_rider(user_id, body.model_dump(exclude_none=True))


@router.get(
    "/{rider_id}",
    response_model=RiderOut,
    summary="Obtener perfil público de un rider",
    description=(
        "Retorna el perfil público de cualquier rider por su ID. No requiere que sea el usuario "
        "autenticado. Lanza 404 si el rider no existe."
    ),
)
async def get_rider(rider_id: str):
    return await service.get_rider_by_id(rider_id)


@router.post(
    "/me/moto",
    response_model=RiderOut,
    summary="Registrar o actualizar moto",
    description=(
        "Crea o actualiza los datos del vehículo del rider autenticado: modelo, año y kilometraje. "
        "Si ya existe una moto registrada, la sobreescribe."
    ),
)
async def update_my_moto(body: MotoUpdate, user_id: str = Depends(get_current_user)):
    return await service.update_moto(user_id, body.model_dump())


@router.post(
    "/{rider_id}/follow",
    response_model=RiderOut,
    summary="Seguir a un rider",
    description=(
        "Agrega al rider autenticado como seguidor del rider especificado. Operación idempotente: "
        "si ya sigue al rider, retorna 200 sin duplicar. Lanza 404 si el rider objetivo no existe."
    ),
)
async def follow(rider_id: str, user_id: str = Depends(get_current_user)):
    return await service.follow_rider(user_id, rider_id)


@router.delete(
    "/{rider_id}/follow",
    response_model=RiderOut,
    summary="Dejar de seguir a un rider",
    description=(
        "Elimina al rider autenticado de la lista de seguidores del rider especificado. Operación "
        "idempotente: si no lo seguía, retorna 200 sin error."
    ),
)
async def unfollow(rider_id: str, user_id: str = Depends(get_current_user)):
    return await service.unfollow_rider(user_id, rider_id)


@router.get(
    "/{rider_id}/stats",
    response_model=StatsOut,
    summary="Estadísticas del rider",
    description=(
        "Retorna métricas agregadas del rider: número de amarres, kilómetros totales y grupos activos. "
        "En esta versión retorna placeholders; se completará en Sprint 2 con datos reales de MS-Amarres."
    ),
)
async def get_stats(rider_id: str):
    return await service.get_stats(rider_id)
```

---

### `ms_riders/service.py` — 151 líneas

```python
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status

from shared.database import get_riders_collection


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def get_rider_by_user_id(user_id: str) -> dict:
    collection = get_riders_collection()
    rider = await collection.find_one({"user_id": user_id})
    if not rider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(rider)


async def get_rider_by_id(rider_id: str) -> dict:
    collection = get_riders_collection()
    try:
        oid = ObjectId(rider_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido")

    rider = await collection.find_one({"_id": oid})
    if not rider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(rider)


async def create_rider(user_id: str, data: dict) -> dict:
    collection = get_riders_collection()

    existing = await collection.find_one({"user_id": user_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes un perfil de rider",
        )

    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "followers": [],
        "following": [],
        "created_at": now,
        "updated_at": now,
        **data,
    }
    result = await collection.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def update_rider(user_id: str, updates: dict) -> dict:
    collection = get_riders_collection()

    updates["updated_at"] = datetime.utcnow()
    result = await collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(result)


async def update_moto(user_id: str, moto: dict) -> dict:
    """Updates vehicle_model, vehicle_year, vehicle_km on the rider document."""
    collection = get_riders_collection()

    patch = {
        "vehicle_model": moto.get("modelo"),
        "vehicle_year": moto.get("año"),
        "vehicle_km": moto.get("km"),
        "updated_at": datetime.utcnow(),
    }
    result = await collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": patch},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(result)


async def follow_rider(follower_user_id: str, target_rider_id: str) -> dict:
    """Idempotent follow: adds follower_user_id to target's followers and target's user_id to follower's following."""
    collection = get_riders_collection()

    target = await get_rider_by_id(target_rider_id)
    target_user_id = target["user_id"]

    if follower_user_id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes seguirte a ti mismo",
        )

    follower = await collection.find_one({"user_id": follower_user_id})
    if not follower:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")

    await collection.update_one(
        {"user_id": follower_user_id},
        {"$addToSet": {"following": target_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )
    await collection.update_one(
        {"user_id": target_user_id},
        {"$addToSet": {"followers": follower_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )

    return await get_rider_by_id(target_rider_id)


async def unfollow_rider(follower_user_id: str, target_rider_id: str) -> dict:
    """Removes follower_user_id from target's followers and target's user_id from follower's following."""
    collection = get_riders_collection()

    target = await get_rider_by_id(target_rider_id)
    target_user_id = target["user_id"]

    await collection.update_one(
        {"user_id": follower_user_id},
        {"$pull": {"following": target_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )
    await collection.update_one(
        {"user_id": target_user_id},
        {"$pull": {"followers": follower_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )

    return await get_rider_by_id(target_rider_id)


async def get_stats(rider_id: str) -> dict:
    await get_rider_by_id(rider_id)  # validates existence
    from ms_amarres.service import get_rider_stats
    from ms_groups.service import get_rider_group_count
    import asyncio
    stats, grupos = await asyncio.gather(
        get_rider_stats(rider_id),
        get_rider_group_count(rider_id),
    )
    return {**stats, "grupos": grupos}
```

---

## Metadata

- **Fecha de extracción:** 2026-04-21 00:00
- **Total archivos incluidos:** 28
- **Total archivos no encontrados:** 0
- **Archivos adicionales incluidos:** ninguno
- **Archivos más grandes:**
  1. `ms_location/service.py` — 225 líneas
  2. `ms_salas/service.py` — 224 líneas
  3. `ms_realtime/ws_bridge.py` — 219 líneas

- **Observaciones del extractor:**

  1. **`ms_salas/service.py::close_sala` — respuesta polimórfica vs schema declarado.** Cuando el amarre se crea correctamente (happy path), la función retorna `{"sala": closed_sala, "amarre": amarre}`. Sin embargo, el router declara `response_model=SalaOut`. En el happy path Pydantic intentará validar un dict con clave `"sala"` como un `SalaOut`, lo que fallará o producirá datos truncados silenciosamente. En el error path (except) retorna el `SalaOut` correcto. El contrato de respuesta es inconsistente.

  2. **`ms_voice/service.py::force_release` — verificación de admin incompleta.** La función llama a `_require_member` (que retorna la sala completa) y luego comprueba `sala["owner_id"] != rider_id`. Funcionalmente correcto, pero `_require_member` ya tiene su propio 403 si no es miembro; el segundo check de owner_id es silencioso. El flujo de permisos está distribuido entre dos lugares.

  3. **`ms_location/router.py::update_position` — función síncrona invocada sin `await`.** `service.update_position` es una función síncrona (no `async def`). En el router se llama sin `await`, lo cual es correcto. Pero cualquier refactor inadvertido a `async def` quebraría el comportamiento de forma silenciosa — rompe la convención "siempre async" del proyecto.

  4. **`datetime.utcnow()` usado en múltiples archivos** (`ms_auth/service.py`, `ms_salas/service.py`, `ms_riders/service.py`, `ms_voice/service.py`, `ms_location/service.py`, etc.). Este método está deprecado desde Python 3.12. El patrón correcto es `datetime.now(timezone.utc)`. `shared/auth.py` ya usa el patrón correcto; el resto del código no.

  5. **Imports en runtime (inline) para romper circulares.** Varios módulos usan imports diferidos dentro de funciones: `ms_auth` importa `ms_riders`, `ms_salas` importa `ms_amarres` y `ms_voice`, `ms_voice` importa `ms_realtime`, `ms_riders` importa `ms_amarres` y `ms_groups`. El patrón es funcional pero genera acoplamiento implícito difícil de rastrear.

  6. **`shared/models.py` casi vacío (6 líneas).** Solo define `NorayBase`. Ningún módulo la importa en los archivos revisados — los modelos de cada módulo extienden directamente `BaseModel`.

  7. **`ms_riders/service.py::get_stats` importa `asyncio` dentro de la función** (línea 145). Import de stdlib dentro de función es inusual y evitable.

  8. **`TrackStore` y `PTTStore` son singletons en memoria** — se pierden en cada restart/redeploy de Railway. Está documentado en comentarios, pero representa un gap funcional real en producción para tracks GPS activos.

  9. **`CORS allow_origins=["*"]`** — apertura total explicitada como decisión de MVP en `main.py`. No es un bug sino una decisión documentada, pero es notable para un revisor de seguridad.

  10. **El módulo `ms_realtime` tiene `router.py` y `schemas.py`** no incluidos en este bundle (no fueron solicitados). El revisor puede pedirlos si son relevantes para el análisis de la capa WebSocket.
