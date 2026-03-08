# Orderly auth/REST gap analysis

Sources: `plutus_terminal/core/exchange/orderly/auth.py:23`, `plutus_terminal/core/exchange/orderly/rest_client.py:22`, `tests/orderly/test_orderly_trader_builder_parity.py:1`, `tests/orderly/test_orderly_fetcher_parser_parity.py:1`, `tests/orderly/test_orderly_websocket_parity.py:1`, `.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:45`.

## Coverage matrix

| Area | Current source behavior | Current test coverage | Gap / implication |
|---|---|---|---|
| Secret decoding | `_decode_base58` rejects empty / invalid chars; `_decode_orderly_secret` requires 32 decoded bytes (`auth.py:23-54`). | None found in `tests/orderly/*.py`. | Add positive decode/sign case and negative invalid-char / wrong-length cases. |
| REST signing preimage | `build_rest_signature_payload` is `timestamp + UPPERCASE_METHOD + path_with_query + serialized_body` (`auth.py:64-72`). This matches the official normalized order (`...test-surface.md:48-52,130`). | None. | High-priority parity test to lock in preimage order and prevent regressions. |
| JSON body normalization | `serialize_body` emits compact JSON and returns `""` for empty bodies (`auth.py:57-61`). `rest_client.py` signs body only for non-`GET`/`DELETE` (`rest_client.py:93-107`). | None. | Add positive POST-body test and negative GET/DELETE-body omission test. |
| Header shaping | Private headers include `orderly-account-id`, `orderly-key`, `orderly-signature`, `orderly-timestamp`, plus method-based `Content-Type` (`auth.py:81-103`). This matches the required header set (`...test-surface.md:48-52`). | None. | Add deterministic header assertions for `GET`, `DELETE`, and `POST`. |
| Query handling for signing | `_build_path_with_query` uses `urlencode(list(params.items()), doseq=True)` and signs `path?query` without base URL (`rest_client.py:132-137`), matching the external guidance (`...test-surface.md:50-52`). | None. | Add parity test for ordered query params and repeated values. |
| Private-request credential guard | `request_private` raises `OrderlyRequestError` when credentials are missing (`rest_client.py:60-78`). | None. | Add a negative unit test; no code change indicated. |
| HTTP transport errors | `_request` re-raises `HTTPStatusError`; `429` is only logged specially (`rest_client.py:109-121`). | None. | Add tests that pin current behavior. If later subtasks want domain-level auth/rate-limit mapping, that is a product decision, not a parity fix from this subtask alone. |
| Application-level API errors | `_raise_for_orderly_error` raises `OrderlyRequestError` only when `payload["success"] is False`; code-bearing errors become `"[code] message"` (`rest_client.py:140-148`). | None. | Add positive success test and negative auth/code-path tests (`-1001`, `-1002`, `-110x`). |
| Auth error classification | External refs call out auth failures as a distinct class to preserve (`...test-surface.md:53-57,98-113`), but current code keeps them in generic `OrderlyRequestError` or raw `HTTPStatusError` (`rest_client.py:112-148`). | None. | Record as a likely mismatch vs ideal classification. Test current behavior first; any exception taxonomy change should be handled explicitly in a later implementation subtask. |
| WebUI-token auth difference | Task context explicitly says current WebUI-token auth differences are intentional and must be preserved (`context.md:10,47`; `...test-surface.md:47,135`). | Indirect only; no auth tests document it. | Tests should validate server-compatible signing/header behavior only. Do not recommend changing onboarding/auth flow just for Python connector parity. |

## Findings

- Current parity tests cover trader payload building, fetcher parsing, and websocket ack behavior, but not auth helpers or REST client behavior (`tests/orderly/test_orderly_trader_builder_parity.py:1`, `tests/orderly/test_orderly_fetcher_parser_parity.py:1`, `tests/orderly/test_orderly_websocket_parity.py:1`).
- Signing preimage order, query inclusion, and header keys appear source-aligned with the official native integration references; this subtask does not identify a required code change there.
- The main likely mismatch is error classification: auth and rate-limit failures are not separated into stable domain-specific buckets today, even though the external reference surface expects that distinction.
- Preserve the intentional WebUI-token auth behavior difference. Connector parity should be enforced at the request/signature surface, not by changing credential onboarding.

## Recommended test targets for follow-up subtasks

1. `auth.py`: positive and negative tests for base58 decode, body serialization, REST preimage construction, REST headers, and websocket auth payload/message.
2. `rest_client.py`: positive and negative tests for signed private requests, query canonicalization, missing credentials, `success: false` payload errors, and `429` / auth failure paths.
3. Keep all tests deterministic with mocked signing/time/HTTP boundaries, per project testing standards (`.opencode/context/core/standards/test-coverage.md:9-29`).
