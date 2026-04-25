# Diagnóstico: Noray4 API (noray4-fastapi)
Fecha: 2026-04-21 | Sprint actual: Sprint 1 (con avance sobre Sprint 2 y 3)

## Health Score: 72/100
El backend está sorprendentemente avanzado para el sprint declarado — todos los módulos hasta Sprint 3 tienen implementación real. Los puntos que bajan el score son riesgos operativos concretos: estado en memoria incompatible con Railway, stats de riders que retornan placeholders, y Firebase auth declarada en CLAUDE.md pero inexistente en el código.

---

## 1. Estado actual

### Features completos
- `ms_auth` — register, login, logout semántico, /me, guest-token (24h TTL)
- `ms_riders` — perfiles, follow/unfollow atómico, moto, stats (⚠️ placeholder)
- `ms_salas` — CRUD, QR token, join, close, miembros, auto-amarre hook
- `ms_chat` — mensajes CRUD, soft delete, ACK, upload Cloudinary, paginación DESC→ASC
- `ms_realtime` — MQTT gateway (paho), WebSocket bridge, audio relay PTT, rate limit 50fps
- `ms_location` — POIs geoespaciales (2dsphere), GPS tracks en memoria, GPX export estructura
- `ms_voice` — canales PTT, WebRTC signaling, force-release admin, PTTStore singleton
- `ms_amarres` — ciclo de vida completo, fotos Cloudinary, clone atómico, likes, feed público
- `ms_groups` — comunidades permanentes, text search, roles admin/rider, stats recalc aggregation

### Features en progreso (% estimado)
- `ms_riders /stats` — 20% (endpoint existe, retorna hardcoded placeholders, sin datos reales de amarres)
- Firebase / Google auth — 0% (declarada en CLAUDE.md, no está en requirements.txt ni en ningún router)
- Logout con token blacklist — 10% (comentario en código lo reconoce para Sprint 2, nada implementado)
- GPX export XML real — 30% (estructura `GPXExport` lista en schemas, la serialización XML no existe)
- Persistencia de tracks GPS — 0% (en memoria pura, se pierde en cada restart de Railway)

### Features planeados no iniciados
- `ms_feed` — Sprint 3, ni la carpeta existe
- `ms_notifications` — Sprint 3, ni la carpeta existe
- Push notifications (FCM/APNs) — no mencionado en código
- Token blacklist (Redis u otro store) — no iniciado

---

## 2. Alineación con CLAUDE.md

| Regla | Estado | Ejemplos |
|-------|--------|---------|
| SIEMPRE async/await en MongoDB | ✅ | Todos los service.py usan `await collection.find_one/insert_one/update_one` |
| NUNCA hardcodear secrets | ⚠️ | `shared/config.py:9` — `JWT_SECRET: str = "changeme"` como default (si .env no existe, arranca con secret inválido en prod) |
| Pydantic v2 `model_config = ConfigDict(...)` | ✅ | `shared/config.py` usa `SettingsConfigDict`, módulos usan `ConfigDict` |
| IDs MongoDB como `str` | ✅ | `shared/dependencies.py:34` — `rider["_id"] = str(rider["_id"])`, patrón replicado en services |
| Errores con `HTTPException` y status codes | ✅ | `shared/exceptions.py`, todos los routers lanzan `HTTPException` con codes correctos |
| Máximo 150 líneas por archivo de servicio | ❌ | `ms_chat/service.py` (357), `ms_salas/service.py` (224), `ms_location/service.py` (225), `ms_voice/service.py` (191), `ms_amarres/service.py` (454), `ms_groups/service.py` (443) — 6 de 9 módulos violan la regla |
| `GET /health` → `{status, version, mqtt}` | ✅ | `main.py:119` — retorna exactamente el shape especificado |
| CORS abierto MVP `allow_origins=["*"]` | ✅ | `main.py` — configurado correctamente |
| Un archivo = una responsabilidad | ⚠️ | `ms_amarres/service.py` (454 líneas) mezcla lifecycle, media, cloning, likes, stats; `ms_groups/service.py` (443) mezcla CRUD, membership, stats, text search |
| Cada módulo con `router.py, schemas.py, service.py, models.py, __init__.py` | ⚠️ | `ms_realtime/` no tiene `models.py`; tiene `mqtt_client.py` y `ws_bridge.py` en lugar de `service.py` — patrón diferente al resto |
| Importar shared directamente | ✅ | Todos los módulos usan `from shared.database import ...`, `from shared.dependencies import ...` |
| Prefijo `/api/v1` en todos los routers | ✅ | `main.py` — `PREFIX = "/api/v1"` aplicado uniformemente |

---

## 3. Deuda técnica detectada

### Severidad alta

- **Estado en memoria no persiste entre reinicios de Railway**
  - `ms_location/track_store.py` — `TrackStore` es un `deque` en memoria, singleton de proceso
  - `ms_voice/ptt_store.py` — `PTTStore` ídem
  - Railway puede matar y reiniciar el contenedor en cualquier momento (free tier, deploys, etc.)
  - GPS tracks activos y estado PTT se pierden silenciosamente. El rider no lo sabe.
  - **Impacto real:** un rider que está en una salida activa pierde su track completo si el pod reinicia

- **`ms_riders/service.py` stats retorna placeholders**
  - `ms_riders/router.py:99` — docstring dice explícitamente "retorna placeholders"
  - Frontend recibirá `km_total: 0`, `amarres_count: 0`, `grupos_count: 0` siempre
  - La colección `amarres` ya existe y tiene los datos necesarios para una aggregation real

- **Firebase / Google auth completamente ausente**
  - `CLAUDE.md` declara `firebase-admin` como dependencia del stack
  - No está en `requirements.txt`, no hay ningún endpoint en `ms_auth/router.py` para Google
  - Si el frontend Flutter usa `google_sign_in`, el backend rechazará todos esos tokens sin ruta de login

- **PTT audio relay no valida contra PTTStore**
  - `ms_realtime/ws_bridge.py` — el bridge retransmite audio de cualquier WebSocket que envíe bytes
  - El `PTTStore` en `ms_voice/ptt_store.py` sabe quién tiene el turno, pero el bridge no lo consulta
  - Cualquier cliente puede enviar audio aunque no tenga el turno PTT

### Severidad media

- **Regla 150 líneas sistemáticamente violada** (ver tabla arriba) — no es un problema funcional hoy pero dificulta mantenimiento y onboarding

- **`ms_salas close` no llama a `ms_location` para persistir GPX**
  - `ms_salas/service.py` — `close_sala()` crea un amarre automático pero no exporta ni limpia el `TrackStore`
  - El amarre auto-creado al cierre no tiene datos GPS aunque `ms_location` los tenga en memoria
  - `ms_location/router.py:155` ya tiene `/salas/{sala_id}/export` y `/clear` — solo falta llamarlos

- **Token logout es semántico, no real**
  - `ms_auth/router.py:50` — comentario explícito: "JWT is stateless; invalidation would require a blocklist"
  - Un token robado de un usuario que "cerró sesión" sigue siendo válido hasta expiración (7 días)

- **`httpx` en requirements.txt sin uso aparente**
  - `requirements.txt:11` — `httpx==0.28.0` declarado
  - No se encontraron imports de httpx en ningún módulo del proyecto
  - Dependencia muerta que aumenta tiempo de build

### Severidad baja

- **`JWT_SECRET` default "changeme"** — `shared/config.py:9`
  - Si Railway no tiene la variable de entorno configurada, la app arranca con un secret conocido
  - Debería hacer `raise ValueError` en startup si `JWT_SECRET == "changeme"` o si está vacío

- **`ms_realtime/` no tiene `models.py`** — rompe la convención de estructura de módulo definida en CLAUDE.md

- **Cobertura de tests: 1/9 módulos**
  - `tests/test_audio_relay.py` cubre solo el WebSocket bridge
  - `ms_auth`, `ms_riders`, `ms_salas`, `ms_chat`, `ms_location`, `ms_voice`, `ms_amarres`, `ms_groups` — sin tests
  - No hay tests de integración con MongoDB (aunque el patrón del proyecto los haría naturales con `mongomock` o `testcontainers`)

---

## 4. Gaps de integración

| Gap | Módulos involucrados | Sugerencia de conexión |
|-----|---------------------|----------------------|
| `close_sala` no exporta GPS al amarre | `ms_salas/service.py` → `ms_location/track_store.py` + `ms_amarres` | En `close_sala()`: llamar `track_store.export_gpx(sala_id)` e incluir el resultado en `amarre_data["gpx_data"]` antes de crear el amarre |
| `close_sala` no limpia TrackStore | `ms_salas/service.py` → `ms_location/track_store.py` | Después de exportar, llamar `track_store.clear_sala(sala_id)` |
| Stats de rider usan placeholders | `ms_riders/service.py` → colección `amarres` | Aggregation directa en `get_stats()`: `db.amarres.aggregate([{$match: {owner_id: rider_id}}, {$group: {_id: null, km_total: {$sum: "$km_total"}, count: {$sum: 1}}}])` |
| PTT audio sin validación de turno | `ms_realtime/ws_bridge.py` → `ms_voice/ptt_store.py` | En `ws_bridge.endpoint()`, antes de retransmitir bytes de audio, consultar `ptt_store.get_speaker(sala_id, canal_id)` y verificar que el emisor tenga el turno |
| Google auth declarado pero inexistente | `ms_auth/` → firebase-admin | Agregar `firebase-admin` a requirements.txt, nuevo endpoint `POST /auth/google` que verifica `id_token` con `firebase_admin.auth.verify_id_token()` y retorna JWT propio |
| Grupos stats no se actualizan automáticamente | `ms_groups/service.py` ← `ms_amarres/service.py` | Al crear/borrar un amarre, llamar `groups_service.update_amarre_stats()` o usar un event hook; actualmente stats solo se actualiza con el endpoint manual `/stats/recalc` |
| `ms_location update_position` publica a MQTT pero no usa `ms_realtime` | `ms_location/router.py` | El endpoint `/salas/{sala_id}/update` guarda en TrackStore pero el docstring dice "publica al topic MQTT" — verificar que la publicación MQTT esté implementada en `service.update_position()` |

---

## 5. Quick wins (< 1h cada uno)

1. **Eliminar `httpx` de requirements.txt** — `requirements.txt:11` — reduce build time y dependencias innecesarias

2. **Fallar startup si `JWT_SECRET` es default** — `shared/config.py` — agregar `@field_validator("JWT_SECRET")` que lance `ValueError` si el valor es `"changeme"` o tiene menos de 16 caracteres

3. **Conectar stats reales en `ms_riders/service.py:get_stats()`** — la colección `amarres` ya existe, es una aggregation de 5 líneas para `km_total` y `amarres_count`; para `grupos_count` consultar `grupos` donde `miembros.rider_id == rider_id`

4. **Crear `ms_realtime/models.py` vacío** — mantiene consistencia de estructura de módulo, costo cero

5. **Añadir `firebase-admin` a requirements.txt** o eliminarlo del CLAUDE.md — la inconsistencia actual es un bug latente para quien lea la documentación

6. **Limpiar TrackStore en `ms_salas/service.py:close_sala()`** — 2 líneas: `from ms_location.track_store import track_store` y `track_store.clear_sala(sala_id)` — evita memory leak de tracks de salas cerradas

---

## 6. Mejoras medias (1-4h)

1. **Exportar GPX al cerrar sala** — `ms_salas/service.py:close_sala()` — recuperar tracks del `TrackStore` antes de crear el amarre automático e incluirlos en `gpx_data`. Desbloquea la feature más importante de amarres. (2h)

2. **Implementar `POST /auth/google`** — verificar Firebase id_token con `firebase_admin`, buscar/crear user en MongoDB, retornar JWT propio. Igual que el flujo de register pero con email verificado por Firebase. (3h)

3. **Validar turno PTT en ws_bridge** — `ms_realtime/ws_bridge.py` — importar `ptt_store` de `ms_voice`, en el handler de bytes de audio verificar si `rider_id` tiene el turno antes de retransmitir. Retornar error JSON si no. (2h)

4. **Dividir `ms_amarres/service.py` (454 líneas)** — extraer `foto_service.py` (upload/delete Cloudinary) y `amarre_social.py` (likes, clone) del service principal. Mantiene `service.py` en ~150 líneas. (2h)

5. **Dividir `ms_groups/service.py` (443 líneas)** — extraer `membership_service.py` (join/leave/kick/role) del service principal. (2h)

---

## 7. Mejoras estratégicas (> 1 día)

1. **Persistir TrackStore y PTTStore en Redis**
   - Impacto: crítico para producción real en Railway
   - Railway puede reiniciar pods en cualquier momento; Railway free tier tiene límites de uptime
   - Solución: usar `aioredis` para almacenar tracks (sorted set por timestamp por rider por sala) y estado PTT (hash por canal)
   - Alternativa más simple: MongoDB con TTL index de 24h para tracks activos
   - Justificación: sin esto, el tracking GPS de riders activos se pierde silenciosamente — es la feature core del producto

2. **Token blacklist para logout real**
   - Impacto: seguridad — tokens de 7 días robados siguen válidos
   - Implementar con Redis SET con TTL = tiempo restante del token
   - El `shared/auth.py:verify_token()` consultaría el blacklist en cada request protegido
   - En términos MVP se puede reducir `JWT_EXPIRE_MINUTES` a 60-120 minutos como mitigación temporal

3. **Tests de integración con MongoDB real (testcontainers)**
   - Impacto: calidad y velocidad de iteración
   - El patrón del proyecto (Motor async, colecciones por función) es ideal para tests con `mongomock_motor` o `testcontainers`
   - Prioridad por módulo: `ms_auth` → `ms_salas` → `ms_amarres` (mayor complejidad de negocio)
   - Sin tests, cada cambio en service.py es un despliegue a producción ciego

4. **Rate limiting en endpoints HTTP**
   - Actualmente solo el WebSocket bridge tiene rate limiting (50fps audio)
   - Los endpoints HTTP de auth (`/register`, `/login`) son vulnerables a fuerza bruta
   - Implementar con `slowapi` (FastAPI-native, basado en limits/redis) en los endpoints sensibles
   - Especialmente importante para `/register` y `/auth/guest-token` que no requieren credenciales

---

## 8. Recomendación de siguiente paso

**Inmediato (esta semana):** Conectar `ms_salas:close_sala()` con el TrackStore de `ms_location` para que los amarres auto-generados incluyan datos GPS reales. Esta es la integración más impactante del sprint actual: el amarre es el artefacto central del producto ("memoria de viajes") y actualmente se crea vacío de datos de ruta. La conexión son ~10 líneas de código y desbloquea el valor real de ms_location y ms_amarres juntos.

**Esta semana también:** Implementar el endpoint `POST /auth/google` con Firebase. Si el frontend Flutter usa `google_sign_in` como flujo principal de onboarding (probable en una app consumer), tener solo login por email/password es un bloqueador de demo. El tiempo estimado es 3h y requiere solo añadir `firebase-admin` a requirements.txt más el handler de verificación. Los módulos de persistencia del track y el blacklist pueden esperar Sprint 2, pero el Google auth no puede esperar si hay demos planificadas.
