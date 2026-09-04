import hashlib
import hmac

from app.core.config import Settings, get_settings


class RazorpayClient:
    """Configuration boundary for Razorpay; no outbound API calls are made here."""

    def __init__(self, settings: Settings) -> None:
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        self.webhook_secret = settings.razorpay_webhook_secret

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not self.webhook_secret or not signature:
            return False
        expected = hmac.new(self.webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


def get_razorpay_client() -> RazorpayClient:
    return RazorpayClient(get_settings())