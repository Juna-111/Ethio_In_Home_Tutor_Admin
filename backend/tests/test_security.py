import hashlib
import hmac
import time
import urllib.parse

from app.auth import validate_telegram_init_data


def _signed_init_data(bot_token: str, auth_date: int | None = None) -> str:
    auth_date = auth_date or int(time.time())
    pairs = [
        ("auth_date", str(auth_date)),
        ("query_id", "AAEAAAE"),
        ("user", '{"id":123456,"first_name":"Test"}'),
    ]
    data = "&".join(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}" for k, v in pairs)
    parsed = urllib.parse.parse_qsl(data, keep_blank_values=True)
    check = "\n".join(f"{k}={v}" for k, v in sorted(parsed))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return f"{data}&hash={digest}"


def test_valid_telegram_init_data_still_passes():
    token = "123456:test-token"
    parsed = validate_telegram_init_data(_signed_init_data(token), token)
    assert parsed is not None
    assert parsed["user"]["id"] == 123456


def test_duplicate_telegram_init_data_keys_are_rejected():
    token = "123456:test-token"
    signed = _signed_init_data(token)
    duplicate = signed.replace("&query_id=AAEAAAE", "&query_id=AAEAAAE&query_id=ATTACKER")
    assert validate_telegram_init_data(duplicate, token) is None


def test_malformed_telegram_hash_is_rejected():
    token = "123456:test-token"
    signed = _signed_init_data(token)
    malformed = signed.rsplit("hash=", 1)[0] + "hash=not-a-valid-hash"
    assert validate_telegram_init_data(malformed, token) is None


def test_oversized_telegram_init_data_is_rejected():
    token = "123456:test-token"
    assert validate_telegram_init_data("a=" + "x" * 20000, token) is None
