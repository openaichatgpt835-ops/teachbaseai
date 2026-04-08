from __future__ import annotations

from typing import Any

import httpx


API_BASE = "https://api.yookassa.ru/v3"


class YooKassaClient:
    def __init__(self, *, shop_id: str, secret_key: str, timeout: float = 30.0):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.timeout = timeout

    def create_payment(self, *, payload: dict[str, Any], idempotence_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, auth=(self.shop_id, self.secret_key)) as client:
            response = client.post(
                f"{API_BASE}/payments",
                headers={
                    "Idempotence-Key": idempotence_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, auth=(self.shop_id, self.secret_key)) as client:
            response = client.get(f"{API_BASE}/payments/{payment_id}")
            response.raise_for_status()
            return response.json()
