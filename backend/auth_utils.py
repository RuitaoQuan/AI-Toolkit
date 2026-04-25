import hashlib
import hmac
import secrets
import uuid


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 120000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False

    if not password_hash.startswith(f"{PASSWORD_SCHEME}$"):
        return hmac.compare_digest(password, password_hash)

    try:
        _, iterations, salt, digest = password_hash.split("$", 3)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return hmac.compare_digest(derived.hex(), digest)
    except (ValueError, TypeError):
        return False


def needs_password_rehash(password_hash: str) -> bool:
    return not password_hash.startswith(f"{PASSWORD_SCHEME}$")


def generate_token(username: str) -> str:
    return f"{username}_{uuid.uuid4().hex}"

