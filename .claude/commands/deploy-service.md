# /deploy-service

Pre-deploy checklist for Railway.

## Usage
```
/deploy-service
```

## Checklist

1. Verify `Procfile` uses `$PORT`: `uvicorn main:app --host 0.0.0.0 --port $PORT`
2. Verify `requirements.txt` is complete and all imports resolve
3. Verify `railway.toml` has the `[[services]]` entry for `noray4-api`
4. Confirm all env vars from `.env.example` are set in Railway dashboard
5. Verify `/health` endpoint returns `{"status": "ok", "version": "...", "mqtt": bool}`
6. Run locally: `uvicorn main:app --reload --port 8000`
7. Check docs at `http://localhost:8000/docs`

## Deploy command (Railway CLI)
```bash
railway up
```

## Environment variables required
See `.env.example` — set all in Railway dashboard under the `noray4-api` service:
- MONGODB_URI
- JWT_SECRET
- JWT_ALGORITHM
- HIVEMQ_HOST, HIVEMQ_PORT, HIVEMQ_USER, HIVEMQ_PASSWORD
- CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
- FIREBASE_PROJECT_ID
