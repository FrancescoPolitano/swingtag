# Technical assumptions register

Rule: every technical assumption made in `SPEC.md` is confirmed by an experiment
before implementation relies on it. This file tracks each one: the claim, where the
spec depends on it, the experiment that tests it, the status and the evidence.

**Status values**

| Status | Meaning |
|---|---|
| CONFIRMED | an experiment in this repository reproduced it; command and result below |
| REFUTED → FIXED | the experiment disproved it; the spec was changed accordingly |
| ORIGIN | observed empirically in the origin system (verification run of 2026-09-08, 41/41 checks); must be re-run on placard infrastructure before release |
| PENDING-AWS | needs a real AWS deployment; tracked as an experiment task in the backlog |
| PENDING-DEVICE | needs a physical phone; tracked as an experiment task in the backlog |

Local experiments live in `spec/experiments/` and `spec/spikes/reference/`. Python
experiments need `qrcode==8.2` (and `opencv-python-headless` for T-13 only).

## Local assumptions

| ID | Assumption | Spec | Experiment | Status | Evidence |
|---|---|---|---|---|---|
| T-01 | NFC normalisation makes macOS (NFD) and Windows (NFC) spellings identical | FR-6 | `e_core.py` t01 | CONFIRMED | "Menù Caffè": NFD 12 code points, NFC 10, equal after NFC |
| T-02 | Reducing HMAC bytes modulo 32 is uniform; the alphabet has 32 symbols without `l o 0 1`; 12 symbols = 60 bits | FR-2, FR-10 | `e_core.py` t02 | CONFIRMED | 256 % 32 = 0; chi² 28.0–33.4 on 2M samples (critical 61.1 at p=0.001) |
| T-03 | Token derivation is deterministic, NFC-insensitive, key-sensitive and unambiguous across the collection/label boundary | FR-10, EC-2 | `e_core.py` t03 | CONFIRMED | 100 identical runs; different key → different token; ("ab","c") ≠ ("a","bc") |
| T-04 | The order-prefix regex accepts the four separators and rejects digits-only names, inner numbers and 7-digit prefixes | FR-5 | `e_core.py` t04 | CONFIRMED | 7/7 cases |
| T-05 | NFKD + ASCII folding transliterates every Latin name into a readable slug | FR-32, EC-9, EC-10 | `e_core.py` t05 | REFUTED → FIXED | NFKD alone drops letters without decomposition ("Straße" → `strae`, "Œuvre" → `uvre`). Spec now applies an explicit table first (ß→ss, æ→ae, œ→oe, ø→o, đ→d, ł→l, þ→th and capitals); with it: `strasse`, `oeuvre`, `olstue`, `lodz`; "★★★" → fallback |
| T-06 | `.url` (INI, BOM, CRLF) and `.webloc` (XML and binary plist) are readable with the standard library; an http/https + host whitelist rejects `javascript:`, `data:`, `file:` and relative URLs | FR-8, EC-12, EC-13 | `spikes/reference/link-parsing/parse_link.py` | CONFIRMED | 11/11 cases |
| T-07 | Terraform resource preconditions on a `yamldecode`d theme stop `plan` with a readable message before any change | FR-12, US-17 | `spikes/reference/theme-validation/` | CONFIRMED | bad colour and unknown `strings` key both fail `plan` with the message |
| T-08 | Terraform `fileset` handles spaces, accents and ` · ` and returns NFC paths even for NFD files on disk | A-4, FR-6 | `spikes/reference/theme-validation/` | CONFIRMED | NFD folder listed as NFC by `terraform console` |
| T-09 | A Terraform `check` block reports a warning without failing the plan | FR-31 | `experiments/e_terraform/` | CONFIRMED | "Warning: Check block assertion failed", plan still 1 to add |
| T-10 | WCAG contrast ratios are computable in HCL | FR-31 | `experiments/e_terraform/` | CONFIRMED | text/background 15.06, primary/background 2.28 (matches a Python reference computation) |
| T-11 | The inherited CSP lets the phone open audio and video directly | FR-36, 10.7 | `spikes/reference/media-csp/` (S1) | REFUTED → FIXED | Chrome blocks `.mp4` ("violates default-src 'none'"); with `media-src 'self'` `.mp4` and `.m4a` load (readyState 4) and images load |
| T-12 | `qrcode` 8.2 is pure Python (no native code) and produces SVG with the path factory | A-6, A-7, FR-37 | `e_core.py` t12 + wheel metadata | CONFIRMED | wheel `qrcode-8.2-py3-none-any.whl`; no mandatory deps (colorama on Windows only); SVG 10,753 bytes, version 5 for a cloudfront URL |
| T-13 | The SVG QR code at level Q decodes back to the exact URL once rendered by a browser | FR-37 | `e_qr_decode.py` | CONFIRMED | OpenCV decodes `https://d1234567890abc.cloudfront.net/3xk9m2p7qhv4` from the Chrome rendering |
| T-14 | `color-mix()` derived tones work with the theme colours, in light and dark | FR-31 | `e_page.py` + `e_serve.py` in Chrome | REFUTED → FIXED | color-mix renders; but a card tone mixed from white stayed light in dark mode (light text on light card). Spec now derives every secondary tone from `text` and `background` only |
| T-15 | A worst-case page (10 buttons, 5 inline icons, logo, notice, footer) stays under 15 KB | FR-30 | `e_page.py` | CONFIRMED | 5,607 bytes |
| T-16 | The page works with the CSP: inline style allowed, same-origin logo allowed, no violations | FR-30, 10.7 | `e_serve.py` in Chrome | CONFIRMED | 0 CSP messages, logo loaded, 0 scripts; buttons 74.8 px high (≥ 56) |
| T-17 | Dates format as specified without OS locales; an invalid timezone raises so a fallback can apply | FR-33, EC-21 | `e_core.py` t17 | CONFIRMED | it `25/09/2026 14:30`, en `25 Sep 2026, 14:30`; `ZoneInfo("Mars/Olympus")` raises |
| T-18 | `Content-Disposition: inline` with the right type opens PDF, image, audio and video in the browser instead of downloading | FR-36 | `e_serve.py` + curl + Chrome | CONFIRMED (desktop Chrome) | headers verified on 5 files; PDF opened in place. Phones: T-62 |
| T-19 | Unknown top-level theme keys can be rejected at plan time | FR-12 | `experiments/e_terraform/` | CONFIRMED | `colour: red` → "unknown keys: colour" |
| T-20 | `jsonencode(yamldecode(theme.yaml))` preserves non-ASCII text | 10.4 | `experiments/e_terraform/` | CONFIRMED | `"header":"Osteria Quattro Mestoli · Città"` unescaped in state output |
| T-21 | A variable validation can reference another variable (domain requires zone) | EC-32, 10.9 | `experiments/e_terraform/` | CONFIRMED, requires Terraform ≥ 1.9 | "hosted_zone_name is required when domain_name is set." Spec prerequisite raised from 1.6 to 1.9 |
| T-22 | The example palettes meet contrast (text/background ≥ 4.5, primary/background ≥ 3 for icons) | 10.11 | Python computation, same formula as T-10 | REFUTED → FIXED | exhibition gold `#c9a227` = 2.28:1. Replaced with `#8c6d0f` = 4.59:1. Restaurant 7.96, nursery 5.45 |
| T-23 | Placeholder media fit the size budget (< 100 KB each) | 10.11 | `say` + ffmpeg, spike of 2026-09-25 | CONFIRMED | M4A 9 s = 79,503 B; MP4 720×1280 8 s = 22,440 B; JPEG 400×300 = 937 B |

## AWS assumptions (need a deployment)

| ID | Assumption | Spec | Status | Prior evidence |
|---|---|---|---|---|
| T-30 | A Lambda package built on macOS (`pip --only-binary`) imports `qrcode` on python3.12 arm64 and writes SVG | A-6 | PENDING-AWS | ORIGIN (same packaging in the origin system) |
| T-31 | The python3.12 Lambda runtime ships the IANA tz database (`ZoneInfo("Europe/Rome")` works) | FR-27, FR-33 | PENDING-AWS | origin used `Europe/Rome` successfully (ORIGIN) |
| T-32 | Single-part upload ETag = MD5 of the body, and `CopyObject` with `MetadataDirective=REPLACE` under SSE-S3 keeps the same ETag | 10.6 steps 7-8, FR-23 | PENDING-AWS | ORIGIN for copy without the new content types |
| T-33 | S3 → SQS notifications filtered on `source/` carry URL-encoded keys (`+`, `%C2%B7`) and an `s3:TestEvent` at setup | 10.5, EC-23, EC-25 | ORIGIN | origin verification |
| T-34 | Writes to `public/` and `config/` produce no queue messages | EC-27 | PENDING-AWS | ORIGIN for `public/`; `config/` is new |
| T-35 | SQS event source with `maximum_concurrency = 2` and `ReportBatchItemFailures` retries only the failed message ids; reserved concurrency throttles pollers | FR-26, 11 | ORIGIN | 43 throttles observed with reserved concurrency 1 |
| T-36 | A 10-file upload of one item produces a single publication thanks to the 30 s window and prefix dedup | EC-1 | ORIGIN | caos run phase 1 |
| T-37 | Upload to visible page change takes ≤ 60 s | FR-20, FR-21, FR-22 | PENDING-AWS | ORIGIN ("within a minute" checks passed) |
| T-38 | CloudFront with OAC and `origin_path=/public` cannot reach `source/` or `config/` | 10.7, 10.8 | PENDING-AWS | ORIGIN for `source/` |
| T-39 | Origin 403 and 404 both surface as the themed `/404.html` with status 404 | FR-35 | ORIGIN | origin verification |
| T-40 | The ES5 CloudFront Function rewrites as tabled and leaves `/_assets/*` untouched | 10.7, EC-33 | PENDING-AWS | ORIGIN for tokens; `/_assets/` is new |
| T-41 | The response headers policy, CSP with `media-src` included, is applied to pages, media and error responses | 10.7 | PENDING-AWS | none for media |
| T-42 | CloudFront with `CachingOptimized` answers `206` with `Accept-Ranges: bytes` on `.mp4` range requests | FR-47 | PENDING-AWS | S4 deferred |
| T-43 | Invalidating `/{token}*` refreshes the page and every resource of the item | 10.6 step 11 | ORIGIN | origin verification |
| T-44 | `aws_lambda_invocation` runs at create and re-runs only when its `triggers` (theme fingerprint, package hash) change | FR-15, FR-41 | PENDING-AWS | none |
| T-45 | Example objects uploaded with `depends_on` on the module all produce notifications (none lost while notifications are being configured) | FR-41 | PENDING-AWS | none; mitigated by the post-upload republish-all |
| T-46 | Without `domain_name` the distribution serves HTTPS on the default certificate; the module plans and applies with the `aws.us_east_1` alias passed and zero ACM resources | FR-44 | PENDING-AWS | none |
| T-47 | `force_destroy = true` deletes a versioned bucket with noncurrent versions | FR-42 | PENDING-AWS | origin needed manual version cleanup (hence the variable) |
| T-48 | Republish-all lists item prefixes with delimiter listings on names containing ` · ` and its synthetic SQS messages are processed like S3 ones | 10.5 | PENDING-AWS | none |
| T-49 | `s3:ListBucket` restricted with `s3:prefix` conditions allows the publisher's delimiter listings of `source/` and `public/` | 10.8 | PENDING-AWS | ORIGIN for listing under both prefixes |
| T-50 | `uploader_principal_arns` can write only under `source/` | FR-46 | ORIGIN | origin policy |
| T-51 | Conservative pruning prevents overlapping runs from deleting fresh writes | EC-28 | ORIGIN | caos run |
| T-52 | Derived tokens make concurrent christening converge on one item | EC-2 | ORIGIN | 9 orphan tokens before the fix, 0 after |
| T-53 | Renaming or moving an item while keeping the token keeps the URL | FR-24, EC-4, EC-5 | ORIGIN | caos phase 3 |
| T-54 | A message in the dead-letter queue raises the CloudWatch alarm | FR-26 | PENDING-AWS | none |
| T-55 | `make demo` completes on a fresh account in under 20 minutes (CloudFront creation included) at near-zero cost | G-2 | PENDING-AWS | none |

## Device assumptions (need a phone)

| ID | Assumption | Spec | Status |
|---|---|---|---|
| T-60 | iOS Safari plays `.m4a` and `.mp4` opened directly under the CSP, over CloudFront range requests | FR-36 | PENDING-DEVICE |
| T-61 | iOS Safari (≥ 16.2) renders `color-mix()` and the layout as Chrome does | FR-31 | PENDING-DEVICE |
| T-62 | Android Chrome opens PDF, image, audio and video from the page (inline or via the system viewer) | FR-36 | PENDING-DEVICE |
| T-63 | A plates-sheet QR code (96 pt side, level Q) scans with a phone camera at arm's length | FR-45 | PENDING-DEVICE |
