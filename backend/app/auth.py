import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Optional

from fastapi import Header, HTTPException, status

from app.config import settings

logger = logging.getLogger("mentorlink.auth")


def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """
    Validates Telegram Mini App initData according to the official Telegram documentation:
    1. Parse query string into key-value pairs.
    2. Extract and remove the 'hash' parameter.
    3. Alphabetically sort remaining parameters and construct data_check_string ('key=value\\n...').
    4. Derive secret_key = HMAC_SHA256("WebAppData", bot_token).
    5. Compare calculated HMAC_SHA256(secret_key, data_check_string) against received hash.
    6. Verify auth_date freshness (< 24 hours / 86400s) to prevent replay attacks.
    """
    if not init_data or not bot_token or len(init_data) > 16384:
        return None

    bot_token = bot_token.strip().strip("'\"")
    init_data = init_data.strip()

    try:
        # Parse query string preserving original values
        parsed_pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        if not parsed_pairs:
            return None
        keys = [key for key, _ in parsed_pairs]
        if len(keys) != len(set(keys)):
            logger.warning("Telegram initData contains duplicate parameters.")
            return None
        data_dict = dict(parsed_pairs)

        received_hash = data_dict.pop("hash", None)
        if not received_hash:
            return None

        # Reconstruct data_check_string with sorted keys
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))

        # Calculate HMAC-SHA256 signature
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(received_hash, calculated_hash):
            logger.warning("Telegram initData HMAC verification failed.")
            return None

        # Verify timestamp freshness and reject future-dated tokens.
        auth_date = int(data_dict.get("auth_date", 0))
        current_time = int(time.time())
        clock_skew = 300
        age = current_time - auth_date
        if auth_date <= 0 or age < -clock_skew or age > 86400:
            logger.warning("Telegram initData expired: auth_date=%s, current=%s", auth_date, current_time)
            return None

        # Parse user JSON if present
        if "user" in data_dict and isinstance(data_dict["user"], str):
            try:
                data_dict["user"] = json.loads(data_dict["user"])
            except json.JSONDecodeError as exc:
                logger.debug("Failed to decode user JSON in initData: %s", exc)

        return data_dict
    except Exception as exc:
        logger.error("Error validating Telegram initData: %s", exc)
        return None


async def get_current_telegram_user(
    authorization: Optional[str] = Header(None)
) -> Optional[int]:
    """
    FastAPI dependency that extracts and validates the Telegram WebApp user from
    the 'Authorization: tma <raw_init_data>' header.

    In production: Enforces strict signature validation.
    In development/preview: Allows unverified fallback only when explicitly permitted.
    """
    if authorization and authorization.lower().startswith("tma "):
        raw_init_data = authorization[4:].strip()
        bot_token = (settings.BOT_TOKEN or "").strip().strip("'\"")
        parsed = validate_telegram_init_data(raw_init_data, bot_token)
        if parsed and "user" in parsed and isinstance(parsed["user"], dict):
            user_id = parsed["user"].get("id")
            if user_id:
                return int(user_id)

        # Token was sent but failed cryptographic validation
        if not settings.ALLOW_UNVERIFIED_WEB_PREVIEW:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Telegram WebApp authentication credentials."
            )

    # Missing Authorization header. Preview access must be explicitly enabled;
    # environment name alone must never weaken identity verification.
    if not settings.ALLOW_UNVERIFIED_WEB_PREVIEW:
        logger.warning(
            "Rejecting request: Missing Telegram WebApp authentication credentials. "
            "(Set ALLOW_UNVERIFIED_WEB_PREVIEW=true only for local preview testing)"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram WebApp authentication credentials."
        )

    return None


async def get_optional_telegram_user(
    authorization: Optional[str] = Header(None),
) -> Optional[int]:
    """Resolve Telegram identity when supplied, while allowing public web intake."""
    if not authorization:
        return None
    if not authorization.lower().startswith("tma "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram WebApp authentication credentials.",
        )

    raw_init_data = authorization[4:].strip()
    bot_token = (settings.BOT_TOKEN or "").strip().strip("'\"")
    parsed = validate_telegram_init_data(raw_init_data, bot_token)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Telegram WebApp authentication credentials.",
        )

    user_data = parsed.get("user")
    if not isinstance(user_data, dict) or user_data.get("id") is None:
        return None
    try:
        return int(user_data["id"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram WebApp user identity.",
        )
