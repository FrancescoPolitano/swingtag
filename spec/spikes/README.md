# Spikes

Phase 1 of the process (see `spec/README.md`): answer the unknowns with small,
throwaway code before writing the spec on top of them. Each spike that answered
its question is promoted to `reference/<name>/` and annotated with two markers:
`PROVES` (the part that validates the approach) and `SHORTCUT` (hardcoded values,
missing error handling, anything the implementation must not copy).

| ID | Question | Answer | Reference |
|---|---|---|---|
| S1 | Does the delivery CSP let a phone open audio and video by direct navigation? | **No, as inherited.** `default-src 'none'` without `media-src` blocks `.mp4` and `.m4a` in Chrome. `media-src 'self'` fixes it; images already pass via `img-src 'self'`. | `reference/media-csp/` |
| S2 | Can link entries (`.url`, `.webloc`) be read with the standard library only, safely? | **Yes.** `configparser` reads `.url` (BOM and CRLF included), `plistlib` reads XML and binary `.webloc`. An `http`/`https` whitelist with a non-empty host rejects `javascript:`, `data:`, `file:` and relative URLs. 11/11 cases pass. | `reference/link-parsing/` |
| S3 | Can Terraform alone validate `theme.yaml` and enumerate content folders with spaces, accents and the ` · ` separator? | **Yes.** `yamldecode` plus resource preconditions stop `plan` with a readable message (bad colour, unknown `strings` key, missing logo). `fileset` handles the names, and Terraform returns paths in NFC even when the file on disk was created in NFD, so object keys uploaded by the examples are always NFC. | `reference/theme-validation/` |
| S4 | Does CloudFront answer range requests on `.mp4` with `206` and play on iOS Safari? | **Deferred to verification.** Needs a real distribution and a real phone. Documented AWS behaviour says yes for S3 origins; the verify script checks `206` and `Accept-Ranges`, and a manual iOS check is part of the release checklist. | none |

Reproduce S2: `python3 reference/link-parsing/parse_link.py`.

Reproduce S3: create folders under `reference/theme-validation/content/` (for example
`Caffè/Menù · k7m2p9x4qzbv/10 Lunch/lunch.pdf`, once in NFC and once in NFD), then
`terraform init && terraform plan`; break a colour in `theme/theme.yaml` to see the
precondition message.

Reproduce S1: put an `.mp4` in a folder, run `python3 reference/media-csp/server.py <dir> 8765`
and open `http://127.0.0.1:8765/<file>.mp4` in Chrome; repeat with
`CSP="... media-src 'self'; ..."`.

## Reference implementation

The system is a generalisation of an existing, working private system (the "origin
system"), which is the de facto reference implementation for the publishing
algorithm, the token scheme and the delivery setup. Its code is not copied into
this repository: its behaviour, decisions and known traps are transcribed in
`spec/SPEC.md` (sections 10 and 11), which is what implementers work from.
