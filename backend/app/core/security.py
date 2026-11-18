"""Password hashing and session token primitives."""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_pwd = PasswordHasher()  # argon2id defaults


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Known bootstrap / guessable passwords that must never stay in use.
DEFAULT_PASSWORDS = frozenset({"Cabinet2026!"})
_WEAK_PASSWORDS = frozenset({
    "password", "password123", "password-123", "password1234",
    "1234567890", "123456789a", "qwerty12345", "admin12345!",
    "clinique123", "dentaire123", "azerty12345", "cabinet2026!",
})
PASSWORD_MIN_LENGTH = 10


def password_problem(password: str) -> str | None:
    """Production password policy. Returns a reason code, or None when acceptable.

    Codes: too_short | too_common | needs_mix. Callers map them to messages.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return "too_short"
    if password.lower() in _WEAK_PASSWORDS or password in DEFAULT_PASSWORDS:
        return "too_common"
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() and not c.isspace() for c in password)
    if not (has_letter and has_digit and has_symbol):
        return "needs_mix"
    return None


def generate_bootstrap_password() -> str:
    """Random one-time password that satisfies password_problem()."""
    while True:
        candidate = f"{secrets.token_urlsafe(9)}-{secrets.randbelow(90) + 10}"
        if password_problem(candidate) is None:
            return candidate
