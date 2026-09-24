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
    if not init_data or not bot_token:
        return None

    try:
        # Parse query string preserving original values
        parsed_pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
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

        # Verify timestamp freshness (max 24 hours old)
        auth_date = int(data_dict.get("auth_date", 0))
        current_time = int(time.time())
        if current_time - auth_date > 86400:
            logger.warning("Telegram initData expired: auth_date=%s, current=%s", auth_date, current_time)
            return None

        # Parse user JSON if present
        if "user" in data_dict and isinstance(data_dict["user"], str):
            try:
                data_dict["user"] = json.loads(data_dict["user"])
            except json.JSONDecodeError:
                pass

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
        bot_token = settings.BOT_TOKEN or ""
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

    # Missing Authorization header
    if not settings.ALLOW_UNVERIFIED_WEB_PREVIEW and settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram WebApp authentication credentials."
        )

    return None
