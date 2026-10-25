import hashlib
import hmac


def sign_payload(secret: str, timestamp: int, body: bytes) -> str:
    """Stripe-style signature header: ``t=<unix>,v1=<hex HMAC-SHA256(secret, "t.body")>``."""
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"
