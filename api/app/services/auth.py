import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.config import settings
from app.models import User

TOKEN_TTL_SECONDS = 30 * 60
PASSWORD_ITERATIONS = 310_000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _b64decode(salt), int(iterations))
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(settings.AUTH_SECRET_KEY.encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode("ascii")
        expected = hmac.new(settings.AUTH_SECRET_KEY.encode(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError("Invalid token signature")
        token_header = json.loads(_b64decode(header))
        claims = json.loads(_b64decode(payload))
        if token_header.get("alg") != "HS256" or int(claims["exp"]) <= int(time.time()):
            raise ValueError("Expired or unsupported token")
        return claims
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid access token") from error
