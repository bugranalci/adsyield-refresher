import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import Request, HTTPException

JWT_SECRET = os.getenv("JWT_SECRET", "adsyield-dev-secret-change-in-production")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Kullanıcılar — email:hash formatında env'den alınır, yoksa default
# Env format: "email1:hash1,email2:hash2"
def _load_users():
    users_env = os.getenv("AUTH_USERS", "")
    if users_env:
        users = {}
        for entry in users_env.split(","):
            email, pw_hash = entry.strip().split(":", 1)
            users[email.strip()] = pw_hash.strip()
        return users

    # Default kullanıcılar (development + initial production)
    return {
        "bnalci@adsyield.com": bcrypt.hashpw(b"Adsyield-2026-*", bcrypt.gensalt()).decode(),
        "ocakir@adsyield.com": bcrypt.hashpw(b"Adsyield-2025-*", bcrypt.gensalt()).decode(),
    }

USERS = _load_users()

def authenticate(email: str, password: str):
    pw_hash = USERS.get(email)
    if not pw_hash:
        return None
    if bcrypt.checkpw(password.encode(), pw_hash.encode()):
        return create_token(email)
    return None

def create_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def auth_middleware(request: Request, call_next):
    """Login ve static dosyalar hariç tüm /api/ isteklerini koru"""
    path = request.url.path

    # Login endpoint'i ve static dosyalar auth gerektirmez
    if path == "/api/login" or not path.startswith("/api/"):
        return await call_next(request)

    # Token kontrolü
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token gerekli")

    token = auth_header.split(" ", 1)[1]
    email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Gecersiz veya suresi dolmus token")

    request.state.user = email
    return await call_next(request)
