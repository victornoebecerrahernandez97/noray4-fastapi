# /new-service

Creates a new module scaffold inside the monolithic app.

## Usage
```
/new-service {nombre}
```

## Steps

1. Create `ms_{nombre}/` with:
   - `__init__.py` — empty
   - `router.py` — `APIRouter(prefix="/{nombre}", tags=["{nombre}"])` with placeholder GET `/`
   - `schemas.py` — empty Pydantic schemas file
   - `service.py` — empty service functions file
   - `models.py` — MongoDB document models (if needed)

2. Register the router in `main.py`:
   ```python
   from ms_{nombre}.router import router as {nombre}_router
   app.include_router({nombre}_router, prefix=PREFIX)
   ```

3. Confirm files created and remind to implement routes in `router.py` using `/add-route`.

## Notes
- No Procfile needed — monolithic architecture, single process
- No separate requirements.txt — all deps in root `requirements.txt`
- No railway.toml changes needed — single `[[services]]` entry covers all modules
- Protected routes use `Depends(get_current_user)` from `shared.dependencies`
