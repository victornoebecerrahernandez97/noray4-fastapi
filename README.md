# noray4-fastapi

**Conecta. Rueda. Vuelve.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)

---

## ¿Qué es Noray4?

Noray4 es una app de comunidad rider para coordinar salidas en moto. Cada salida es una sala de comunicación en tiempo real con voz push-to-talk, mapa compartido entre la tripulación, chat con archivos y al finalizar, un registro del viaje guardado como memoria colectiva.

Este repositorio contiene el backend — una API REST construida con FastAPI, organizada en microservicios independientes, cada uno con su propio router, modelos y lógica de negocio.

---

## Stack

| Capa           | Tecnología                  |
|----------------|-----------------------------|
| Framework      | FastAPI (Python 3.11+)      |
| Base de datos  | MongoDB Atlas M0 + Motor    |
| Deploy         | Railway                     |
| Mensajería     | HiveMQ Cloud (MQTT)         |
| Auth externa   | Firebase Auth (Google Sign-In) |
| Media          | Cloudinary                  |

---

## Arquitectura

El backend se divide en 11 microservicios. Cada uno expone un `APIRouter` con prefijo propio y se monta en `main.py`.

| Servicio            | Responsabilidad                                          |
|---------------------|----------------------------------------------------------|
| `ms_auth`           | Registro, login, verificación de token Firebase/JWT      |
| `ms_riders`         | Perfil del rider, motos, configuración de cuenta         |
| `ms_salas`          | Crear, unirse y cerrar salidas (salas activas)           |
| `ms_realtime`       | WebSocket hub — sincronización de estado en tiempo real  |
| `ms_chat`           | Mensajes de texto y archivos dentro de una salida        |
| `ms_location`       | Posiciones GPS en tiempo real, POIs compartidos          |
| `ms_voice`          | Sesiones de voz push-to-talk (señalización)              |
| `ms_amarres`        | Registros de viajes — historial y memoria de salidas     |
| `ms_groups`         | Tripulaciones — grupos persistentes de riders            |
| `ms_feed`           | Feed social: actividad, registros públicos               |
| `ms_notifications`  | Push notifications y notificaciones internas             |

---

## Estructura del monorepo

```
noray4-fastapi/
├── main.py                  # App principal, CORS, montaje de routers
├── requirements.txt
├── .env
├── .env.example
│
├── shared/                  # Código compartido entre servicios
│   ├── database.py          # Conexión Motor/MongoDB
│   ├── auth.py              # get_current_user, verify_token
│   └── config.py            # Settings desde .env
│
├── ms_auth/
│   ├── router.py
│   ├── models.py
│   ├── schemas.py
│   └── service.py
│
├── ms_riders/
├── ms_salas/
├── ms_realtime/
├── ms_chat/
├── ms_location/
├── ms_voice/
├── ms_amarres/
├── ms_groups/
├── ms_feed/
└── ms_notifications/
```

Sprint 1 activo: `ms_auth`, `ms_riders`, `ms_salas`, `ms_realtime`.

---

## Primeros pasos

### 1. Clonar el repositorio

```bash
git clone https://github.com/noebecerra/noray4-fastapi.git
cd noray4-fastapi
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 4. Correr el servidor localmente

```bash
uvicorn main:app --reload --port 8000
```

Documentación interactiva disponible en `http://localhost:8000/docs`.

---

## Variables de entorno

| Variable              | Descripción                                      |
|-----------------------|--------------------------------------------------|
| `MONGO_URI`           | URI de conexión a MongoDB Atlas                  |
| `JWT_SECRET`          | Secreto para firmar tokens JWT                   |
| `JWT_EXPIRE_MINUTES`  | Duración del token en minutos (default: 10080)   |
| `FIREBASE_PROJECT_ID` | ID del proyecto Firebase para verificar tokens   |
| `SERVICE_NAME`        | Nombre del microservicio activo                  |
| `PORT`                | Puerto de escucha (default: 8000)                |
| `HIVEMQ_HOST`         | Host del broker MQTT                             |
| `HIVEMQ_PORT`         | Puerto MQTT TLS (default: 8883)                  |
| `HIVEMQ_USER`         | Usuario HiveMQ Cloud                             |
| `HIVEMQ_PASSWORD`     | Contraseña HiveMQ Cloud                          |
| `CLOUDINARY_URL`      | URL de conexión a Cloudinary                     |
| `ENVIRONMENT`         | `development` o `production`                     |

---

## Roadmap

### Fase 1 — MVP
Autenticación, perfil de rider, salidas en tiempo real, chat básico, voz PTT.

### Fase 2 — Feedback loop
Registros de viajes (amarres), historial, mapa con trayectorias, mejoras UX basadas en uso real.

### Fase 3 — Lanzamiento público
Grupos (tripulaciones), feed social, notificaciones push, onboarding pulido.

### Fase 4 — Crecimiento
Salidas programadas, descubrimiento de rutas, integraciones externas, monetización.

---

## Autor

**Noé Becerra** — Founder de Noray4, biker y desarrollador.

Noray4 nació de la necesidad real de coordinar salidas en moto con la tripulación — sin depender de grupos de WhatsApp ni apps genéricas que no entienden lo que es rodar en grupo.
