# Staging bootstrap (Windows)
$env:DATABASE_URL = "sqlite:///./staging.db"
$env:JWT_SECRET = "change-me"
$env:ALLOW_REGISTRATION = "1"
$env:CORS_ORIGINS = "http://localhost:5500"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
