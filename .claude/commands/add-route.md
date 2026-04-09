# /add-route

Adds a new route to an existing module.

## Usage
```
/add-route {module} {METHOD} {path} {description}
```

## Example
```
/add-route riders GET /me "Get authenticated rider profile"
```

## Steps

1. Open `ms_{module}/router.py`
2. Add the route to the `router` with proper:
   - HTTP method decorator
   - Path
   - `response_model` if applicable
   - `Depends(get_current_user)` or `Depends(get_current_rider)` for protected routes
   - Docstring / `summary` parameter
3. Implement the handler — keep it thin, delegate to `service.py` if logic grows
4. If `service.py` doesn't exist yet, create it alongside `router.py`

## Rules
- Protected routes: always `user_id: str = Depends(get_current_user)`
- For routes needing full rider profile: `rider = Depends(get_current_rider)`
- Return `HTTPException` with correct status codes on errors
- MongoDB IDs must be serialized as `str`
- Keep `router.py` under 150 lines — extract business logic to `service.py`
- Import shared deps from `shared.dependencies`, `shared.database`, `shared.config`
