import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return "r_" + secrets.token_urlsafe(48)


def new_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def ensure_jwt_keys() -> tuple[str, str]:
    settings = get_settings()
    private_path = Path(settings.jwt_private_key_path)
    public_path = Path(settings.jwt_public_key_path)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    if not private_path.exists() or not public_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        public_path.write_bytes(
            key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    return private_path.read_text(), public_path.read_text()


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    private_key, _ = ensure_jwt_keys()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": settings.jwt_key_id})


def decode_access_token(token: str) -> dict:
    _, public_key = ensure_jwt_keys()
    return jwt.decode(token, public_key, algorithms=["RS256"])


def badge_fernet() -> Fernet:
    settings = get_settings()
    raw = settings.badge_token_enc_key.encode() if settings.badge_token_enc_key else b""
    digest = hashlib.sha256(raw or b"nmc-local-badge-key").digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(token: str) -> str:
    return badge_fernet().encrypt(token.encode()).decode()


def decrypt_token(value: str) -> str:
    return badge_fernet().decrypt(value.encode()).decode()
