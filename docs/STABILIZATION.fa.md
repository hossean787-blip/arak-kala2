# ممیزی تثبیت — 2026-11-25

Baseline: `ef9a3f21bdbdd9fa798c8de12d23ab1d41b81abe` (main). Active backend Django; Android admin Kotlin/Compose; legacy Android WebView retained. No previous GitHub Actions runs at audit time. Main was unprotected and public. Archive includes separate Sepas files: not imported or used; owner should review exposure and independently approve any archive relocation or visibility change.

## Candidate fixes
- Service-level positive quantity and nonempty cart validation; compare order replay items at transaction boundary.
- Require expected_stock for manager PATCH changing stock. Android already sends it when changing existing stock.
- Deduplicate saved cart; tolerate unavailable localStorage; retain order retry fingerprint/token during modal reopen or refresh in same tab; no raw address/phone stored; subtract purchased quantities.
- Regression tests for service replay and invalid quantities and manager stock conflicts.
- CI validates Django migrations, tests, JS syntax, static collection and Android debug build/lint. Existing dependency pins preserved pending CI evidence.

## Evidence and gates
Static review of Django settings/URLs/models/services/API/forms/views, storefront JS, Android build config and targeted Kotlin stock/token code, README/test files. Existing docs report 8 tests and debug APK build on prior environment, but QA.json contains older unexecuted results. Fresh CI evidence required. Local git clone failed DNS; Django missing. No current browser/device or production tests. Do not merge until CI succeeds; do not claim release readiness.

## Remaining P0/P1
- Confirm requirements pins install and security audit; review full git history for credentials, rotate actual secrets if discovered, do not copy archives across projects.
- Enforce login rate limiting at gateway, password recovery/phone verification, HTTPS, media serving and DB backup/restore; configure actual production domain. Review manager web login and legacy guest order routes against approved scope.
- Payment and delivery not configured; never expose trial checkout as a live paid store.
- Reproduce mobile image problem on real viewport/device; gallery and visual improvements in next phase.
- APK release requires actual HTTPS endpoint and signing; debug APK not release. Run real Android device and end-to-end tests.
- Main branch protection and repository visibility changes require explicit owner approval; no access policy changes made.
