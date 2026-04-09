from app.utils.security import (
    hash_password, verify_password, create_access_token,
    decode_access_token, create_refresh_token, hash_token,
    generate_invite_token,
)
from app.utils.slug import generate_slug
from uuid import uuid4


def test_password_hash_and_verify():
    pw = "mein-sicheres-passwort"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("falsch", hashed)


def test_access_token_roundtrip():
    user_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(user_id, tenant_id)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["type"] == "access"


def test_decode_invalid_token():
    assert decode_access_token("garbage.token.here") is None


def test_refresh_token_generation():
    raw, hashed, expires = create_refresh_token()
    assert len(raw) > 32
    assert hashed == hash_token(raw)
    assert expires is not None


def test_invite_token():
    t1 = generate_invite_token()
    t2 = generate_invite_token()
    assert t1 != t2
    assert len(t1) > 20


def test_slug_generation():
    assert generate_slug("Test Firma GmbH") == "test-firma-gmbh"
    assert generate_slug("  Spaces  Everywhere  ") == "spaces-everywhere"
    assert generate_slug("UPPER-case") == "upper-case"
    assert generate_slug("sonder!zeichen@hier") == "sonderzeichenhier"
    assert generate_slug("") == "workspace"
