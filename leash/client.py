"""Thin Airwallex REST client: token caching and idempotent creates."""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

SANDBOX_URL = "https://api.sandbox.airwallex.com"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class AirwallexError(Exception):
    def __init__(self, status: int, body: dict | str):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


class AirwallexClient:
    def __init__(self, client_id: str, api_key: str, base_url: str = SANDBOX_URL):
        self._client_id = client_id
        self._api_key = api_key
        self._http = httpx.Client(base_url=base_url, timeout=30)
        self._token: str | None = None
        self._token_expires = datetime.min.replace(tzinfo=timezone.utc)

    @classmethod
    def from_env(cls) -> "AirwallexClient":
        client_id = os.environ.get("AIRWALLEX_CLIENT_ID")
        api_key = os.environ.get("AIRWALLEX_API_KEY") or os.environ.get("AIRWALLEX_API")
        if not client_id or not api_key:
            raise SystemExit("Set AIRWALLEX_CLIENT_ID and AIRWALLEX_API_KEY in .env")
        return cls(client_id, api_key)

    def _auth_headers(self) -> dict:
        # Tokens last 30 minutes; refresh a minute early.
        if self._token is None or datetime.now(timezone.utc) >= self._token_expires:
            resp = self._http.post(
                "/api/v1/authentication/login",
                headers={"x-client-id": self._client_id, "x-api-key": self._api_key},
            )
            if resp.status_code >= 400:
                raise AirwallexError(resp.status_code, _body(resp))
            data = resp.json()
            self._token = data["token"]
            self._token_expires = datetime.now(timezone.utc) + timedelta(minutes=29)
        return {"Authorization": f"Bearer {self._token}"}

    def get(self, path: str, params: dict | None = None) -> dict | list:
        resp = self._http.get(path, params=params, headers=self._auth_headers())
        if resp.status_code >= 400:
            raise AirwallexError(resp.status_code, _body(resp))
        return resp.json()

    def post(self, path: str, body: dict, request_id: str | None = None, attempts: int = 3) -> dict:
        """POST a create. One request_id per operation, reused on every retry."""
        if request_id is not None:
            body = {**body, "request_id": request_id}
        for attempt in range(1, attempts + 1):
            try:
                resp = self._http.post(path, json=body, headers=self._auth_headers())
            except httpx.TransportError:
                if attempt == attempts:
                    raise
            else:
                if resp.status_code not in RETRYABLE_STATUS or attempt == attempts:
                    if resp.status_code >= 400:
                        raise AirwallexError(resp.status_code, _body(resp))
                    return resp.json()
            time.sleep(2 ** attempt)
        raise AssertionError("unreachable")


def new_request_id() -> str:
    return str(uuid.uuid4())


def _body(resp: httpx.Response) -> dict | str:
    try:
        return resp.json()
    except ValueError:
        return resp.text
