from fastapi import APIRouter, Depends, status

from shared.dependencies import get_current_user
from ms_auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ms_auth import service

router = APIRouter(prefix="/auth", tags=["auth"])


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
    return await service.create_guest_token()
