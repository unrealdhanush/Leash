"""Visa Trusted Agent Protocol message signatures (RFC 9421, Ed25519), for both sides of a checkout.

Follows Visa's merchant requirements: covered components @authority and @path; created, expires, keyid,
alg, nonce and tag parameters; tag agent-browser-auth or agent-payer-auth; a window of at most 8 minutes;
no nonce reused within that window. Visa's real key directory needs partner credentials, so KeyDirectory
stands in for it."""

import base64
import hashlib
import re
import secrets
import time
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

BROWSE = "agent-browser-auth"
PAY = "agent-payer-auth"
MAX_WINDOW = 8 * 60
COMPONENTS = ("@authority", "@path")
REQUIRED_PARAMS = ("created", "expires", "keyid", "alg", "nonce", "tag")


class AgentIdentity:
    def __init__(self, key: Ed25519PrivateKey | None = None):
        self._key = key or Ed25519PrivateKey.generate()
        raw = self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.keyid = hashlib.sha256(raw).hexdigest()[:16]

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._key.public_key()

    def jwk(self) -> dict:
        raw = self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return {"kty": "OKP", "crv": "Ed25519", "kid": self.keyid, "alg": "Ed25519", "use": "sig", "x": _b64url(raw)}

    def sign(self, authority: str, path: str, tag: str, nonce: str | None = None, ttl: int = MAX_WINDOW) -> dict:
        """Signature-Input and Signature headers for a request to authority + path."""
        created = int(time.time())
        params = {
            "created": created,
            "expires": created + ttl,
            "keyid": self.keyid,
            "alg": "Ed25519",
            "nonce": nonce or secrets.token_urlsafe(16),
            "tag": tag,
        }
        signature_input = _signature_params(params)
        base = _signature_base(authority, path, signature_input)
        signature = base64.b64encode(self._key.sign(base.encode())).decode()
        return {"Signature-Input": f"sig2={signature_input}", "Signature": f"sig2=:{signature}:"}


@dataclass
class KeyDirectory:
    """Stand-in for Visa's key store: GET /keys?keyID=... returns a JWK set."""

    keys: dict[str, dict] = field(default_factory=dict)

    def register(self, identity: AgentIdentity) -> None:
        self.keys[identity.keyid] = identity.jwk()

    def lookup(self, keyid: str) -> dict | None:
        return self.keys.get(keyid)


class Verifier:
    def __init__(self, directory: KeyDirectory):
        self._directory = directory
        self._seen_nonces: dict[str, float] = {}

    def verify(self, headers: dict, authority: str, path: str, required_tag: str) -> str | None:
        """None if the request is from a trusted agent with the required intent, else the reason it is not."""
        signature_input = headers.get("signature-input", "")
        signature = headers.get("signature", "")
        m = re.fullmatch(r'sig2=(\("@authority" "@path"\)(?:;[a-z]+=(?:"[^"]*"|\d+))+)', signature_input)
        s = re.fullmatch(r"sig2=:([A-Za-z0-9+/=]+):", signature)
        if not m or not s:
            return "no trusted agent signature"
        params = _parse_params(m.group(1))
        if missing := [p for p in REQUIRED_PARAMS if p not in params]:
            return f"missing signature parameters: {', '.join(missing)}"
        if params["tag"] not in (BROWSE, PAY):
            return "not a trusted agent tag"
        if params["tag"] != required_tag:
            return f"tag {params['tag']} does not state intent to pay"
        now = time.time()
        created, expires = int(params["created"]), int(params["expires"])
        if not created <= now < expires or expires - created > MAX_WINDOW:
            return "signature outside its time window"
        self._seen_nonces = {n: t for n, t in self._seen_nonces.items() if now - t < MAX_WINDOW}
        if params["nonce"] in self._seen_nonces:
            return "nonce already used (replay)"
        jwk = self._directory.lookup(params["keyid"])
        if jwk is None or jwk["alg"] != params["alg"]:
            return "unknown agent key"
        public_key = Ed25519PublicKey.from_public_bytes(_b64url_decode(jwk["x"]))
        try:
            public_key.verify(base64.b64decode(s.group(1)), _signature_base(authority, path, m.group(1)).encode())
        except InvalidSignature:
            return "signature does not match the request"
        self._seen_nonces[params["nonce"]] = now
        return None


def _signature_params(params: dict) -> str:
    components = " ".join(f'"{c}"' for c in COMPONENTS)
    rendered = "".join(f";{k}={v}" if isinstance(v, int) else f';{k}="{v}"' for k, v in params.items())
    return f"({components}){rendered}"


def _signature_base(authority: str, path: str, signature_params: str) -> str:
    return f'"@authority": {authority}\n"@path": {path}\n"@signature-params": {signature_params}'


def _parse_params(s: str) -> dict:
    return {k: quoted or number for k, quoted, number in re.findall(r';([a-z]+)=(?:"([^"]*)"|(\d+))', s)}


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
