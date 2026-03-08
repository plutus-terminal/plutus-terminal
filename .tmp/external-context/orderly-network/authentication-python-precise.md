---
source: Context7 API + Orderly official docs
library: Orderly Network
package: orderly-network
topic: precise API authentication details for Python (REST + WebSocket)
fetched: 2026-02-07T00:00:00Z
official_docs: https://orderly.network/docs/build-on-omnichain/evm-api/api-authentication
---

# Orderly auth details (implementation-ready)

## 1) `orderly-key` and secret/private key format

- `orderly-key` header value format is `ed25519:<base58-encoded-public-key>`.
- Python official sample generates header key with:
  - `b58encode(public_key_bytes)`
  - then prefixing `ed25519:`.
- Python official sample loads secret from env var `ORDERLY_SECRET` as base58 and then does:
  - `key = b58decode(os.environ.get("ORDERLY_SECRET"))`
  - `Ed25519PrivateKey.from_private_bytes(key)`
- This means Orderly Python sample expects the secret as base58 text that decodes to raw Ed25519 private bytes accepted by `from_private_bytes`.
- Docs do not describe PEM or hex for REST signing secret; official Python auth sample does not use PEM.

## 2) Exact signing payload format

### REST

- Official API-auth docs define normalization in this exact order:
  1. `timestamp_ms`
  2. `HTTP_METHOD_UPPERCASE`
  3. `path_with_query` (no scheme/host)
  4. optional JSON body string (if body exists)
- Canonical example from docs:
  - `1649920583000POST/v1/order{"symbol": "PERP_ETH_USDC", "order_type": "LIMIT", "order_price": 1521.03, "order_quantity": 2.11, "side": "BUY"}`
- Signing algorithm: Ed25519 over UTF-8 bytes of normalized message.

### WebSocket private auth

- WS auth doc states request method/path/body are blank for auth.
- Therefore WS auth signing message is only the timestamp (as string/bytes).
- Auth can be sent either:
  - in `auth` event params (`orderly_key`, `sign`, `timestamp`), or
  - in connection query string: `?orderly_key=...&timestamp=...&sign=...`.

## 3) Raw private key bytes vs seed

- Official Python sample calls `Ed25519PrivateKey.from_private_bytes(decoded_secret)`.
- In `cryptography`, this API takes 32-byte private key material for Ed25519.
- Orderly docs do not separately define "seed vs expanded 64-byte secret" wording; they only show this API usage.
- Practical expectation from official sample: provide base58 text that decodes to bytes accepted by `from_private_bytes` (32 bytes).

## 4) URL-safe base64 and padding

- API-auth docs require signature encoded in "base64 url-safe" format.
- Python sample uses `base64.urlsafe_b64encode(signature).decode("utf-8")` (typically includes `=` padding).
- TypeScript sample uses `Buffer.from(sig).toString("base64url")` (commonly no padding).
- Docs do not explicitly specify padding policy; they only specify URL-safe base64.

## 5) Required and optional headers

- Required REST headers from API-auth docs:
  - `Content-Type`
  - `orderly-account-id`
  - `orderly-key`
  - `orderly-signature`
  - `orderly-timestamp`
- `Content-Type` rules:
  - `GET` / `DELETE`: `application/x-www-form-urlencoded`
  - others (`POST`, `PUT`, etc.): `application/json`
- Timestamp validity check: request rejected if `orderly-timestamp` differs from server time by >= 300 seconds.
- No optional `recv window` header is documented in current Orderly API-auth page or WS-auth page.

## Python snippets (minimal)

```python
from base58 import b58decode, b58encode
from base64 import urlsafe_b64encode
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def encode_orderly_key(public_key_bytes: bytes) -> str:
    return f"ed25519:{b58encode(public_key_bytes).decode('utf-8')}"

def sign_rest(secret_b58: str, ts_ms: int, method: str, path_with_query: str, body_json: str = ""):
    sk = Ed25519PrivateKey.from_private_bytes(b58decode(secret_b58))
    payload = f"{ts_ms}{method.upper()}{path_with_query}{body_json}"
    sig = urlsafe_b64encode(sk.sign(payload.encode("utf-8"))).decode("utf-8")
    return sig

def sign_ws_auth(secret_b58: str, ts_ms: int):
    sk = Ed25519PrivateKey.from_private_bytes(b58decode(secret_b58))
    return urlsafe_b64encode(sk.sign(str(ts_ms).encode("utf-8"))).decode("utf-8")
```

## Source links used

- https://orderly.network/docs/build-on-omnichain/evm-api/api-authentication
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/authentication
- https://orderly.network/docs/build-on-omnichain/user-flows/wallet-authentication
