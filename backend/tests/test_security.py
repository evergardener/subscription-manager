import pytest
from pydantic import ValidationError

from app.auth.security import hash_password, new_secret, sha256, verify_password
from app.core.config import Settings


def test_password_hash_and_token_digest_do_not_store_plaintext() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    assert password not in password_hash
    assert verify_password(password_hash, password)
    assert not verify_password(password_hash, "incorrect password")
    token = new_secret("hsm_")
    assert token.startswith("hsm_")
    assert token not in sha256(token)


def test_production_requires_secure_session_cookie() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE must be true"):
        Settings(environment="production", cookie_secure=False)
    assert Settings(environment="production", cookie_secure=True).cookie_secure
