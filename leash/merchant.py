"""A mock vendor checkout on localhost. It only charges the card for a trusted agent that signed its intent to pay."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from leash.sandbox import CardSimulator
from leash.tap import PAY, AgentIdentity, Verifier

CHECKOUT_PATH = "/checkout"


class MockMerchant:
    def __init__(self, verifier: Verifier, simulator: CardSimulator, merchant_category: str):
        self._verifier = verifier
        self._simulator = simulator
        self._mcc = merchant_category
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.authority = f"127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> "MockMerchant":
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()

    def _handler(self):
        merchant = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != CHECKOUT_PATH:
                    return self._reply(404, {"error": "not found"})
                headers = {k.lower(): v for k, v in self.headers.items()}
                reason = merchant._verifier.verify(headers, self.headers["Host"], self.path, PAY)
                if reason:
                    return self._reply(401, {"error": reason})
                order = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                result = merchant._simulator.authorize(order["card_id"], order["amount"], order["currency"], merchant._mcc)
                self._reply(200, {"accepted": result.accepted, "failure_reason": result.failure_reason})

            def _reply(self, status: int, body: dict):
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        return Handler


def sign_checkout(identity: AgentIdentity, authority: str, tag: str = PAY) -> dict:
    return identity.sign(authority, CHECKOUT_PATH, tag)


def place_order(authority: str, headers: dict, order: dict) -> tuple[int, dict]:
    """The agent's side of checkout: post the order with its signature headers (empty for an unsigned request)."""
    resp = httpx.post(f"http://{authority}{CHECKOUT_PATH}", json=order, headers=headers, timeout=30)
    return resp.status_code, resp.json()
