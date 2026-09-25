# swingtag: test plan

**Status:** draft for review · **Version:** 0.1 · **Date:** 2026-09-25 · **Spec:** SPEC 1.0

Phase 4 of the process: the tests are listed, named and specified with input and expected
output before the implementation plan. This list is the definition of done. A test that
cannot be stated with a concrete input and an observable output is not in this plan.

## 1. Levels, tools and conventions

| Level | Prefix | Runs | Tool | Where |
|---|---|---|---|---|
| Unit | `U-` | every commit, CI | pytest (Python 3.12), no network | `tests/unit/test_<module>.py` |
| Terraform | `TF-` | every commit, CI | `terraform test` with `mock_provider "aws"` (T-24) | `terraform/tests/*.tftest.hcl` |
| Rewrite function | `JS-` | every commit, CI | Node, `vm` context (T-25) | `terraform/functions/test_rewrite.mjs` |
| Live | `L-` | before release, on a deployed example in the lab account | `make verify` plus the procedures below (AWS CLI + curl) | `scripts/verify.sh`, this document |
| Device | `D-` | before release | a real iPhone and Android phone | this document |

Conventions:

- Unit test function names are the lowercase test name: `U-CONV-03 parse_order_dot` is
  `def test_parse_order_dot()` in `tests/unit/test_convention.py`.
- AWS clients in unit tests are hand-written stubs in `tests/unit/stubs.py` (`StubS3`,
  `StubCloudFront`, `StubSQS`) that record calls and keep objects in a dict keyed by key,
  with `ETag` = MD5 of the body, `LastModified` settable, and paginated listing (page size
  settable). No moto, no network.
- A fixed secret `"test-secret"` and a fixed clock are used wherever tokens or dates appear.
- "Logged" means a record captured by pytest's `caplog` at WARNING (anomalies) or INFO.
- Sizes are bytes of the UTF-8 encoded output.

Definition of done: every `U-`, `TF-` and `JS-` test passes in CI; every `L-` test passes on
each of the three examples; every `D-` test is recorded with device, OS and browser version.

## 2. Unit tests

### 2.1 convention.py

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-CONV-01 | normalize_merges_nfd | `normalize("Men" + "ù")` and `normalize("Menù")` | equal strings, length 4 | FR-6, EC-8 |
| U-CONV-02 | parse_order_space | `"10 Lunch"` | `(10, "Lunch")` | FR-5 |
| U-CONV-03 | parse_order_dot | `"10. Lunch"` | `(10, "Lunch")` | FR-5 |
| U-CONV-04 | parse_order_dash | `"10 - Lunch"` | `(10, "Lunch")` | FR-5 |
| U-CONV-05 | parse_order_paren | `"10) Lunch"` | `(10, "Lunch")` | FR-5 |
| U-CONV-06 | parse_order_digits_only | `"10"` | `(None, "10")` | FR-5 |
| U-CONV-07 | parse_order_inner_number | `"Table 3 north"` | `(None, "Table 3 north")` | FR-5 |
| U-CONV-08 | parse_order_seven_digits | `"1234567 X"` | `(None, "1234567 X")` | FR-5 |
| U-CONV-09 | sort_numbered_first | labels `["b", "20 a", "a", "10 c"]` sorted by `sort_key(*parse_order(x))` | `["10 c", "20 a", "a", "b"]` | FR-5 |
| U-CONV-10 | sort_case_insensitive | `["beta", "Alpha"]` unnumbered | `["Alpha", "beta"]` | FR-5 |
| U-CONV-11 | ignored_dot_underscore | `".hidden"`, `"_draft.pdf"` | `is_ignored` True for both | FR-9 |
| U-CONV-12 | ignored_system_files | `".DS_Store"`, `"Thumbs.db"`, `"desktop.ini"`, `"Icon\r"` | True for all | FR-9 |
| U-CONV-13 | not_ignored_regular | `"menu.pdf"` | False | FR-9 |
| U-CONV-14 | token_alphabet_and_length | `token_for("C", "L", "test-secret")` | 12 chars, all in `TOKEN_ALPHABET`, none of `l o 0 1` | FR-2 |
| U-CONV-15 | token_deterministic | same call twice | equal | FR-10, EC-2 |
| U-CONV-16 | token_key_sensitive | secrets `"a"` and `"b"` | different tokens | FR-10 |
| U-CONV-17 | token_nfc_insensitive | collection `"Città"` in NFC and NFD | equal tokens | FR-6, FR-10 |
| U-CONV-18 | token_boundary | `("ab","c")` vs `("a","bc")` | different tokens | FR-10 |
| U-CONV-19 | split_item_valid_token | `"Olivo · 3xk9m2p7qhv4"` | `("Olivo", "3xk9m2p7qhv4")` | FR-3 |
| U-CONV-20 | split_item_last_separator | `"Olivo · north · 3xk9m2p7qhv4"` | `("Olivo · north", "3xk9m2p7qhv4")` | FR-3 |
| U-CONV-21 | split_item_invalid_tail | `"Olive · north terrace"` | `("Olive · north terrace", None)` | FR-3 |
| U-CONV-22 | split_item_bad_alphabet | `"Olivo · 3xk9m2p7qhv0"` (contains `0`) | label is the whole name, token None | FR-2, FR-3 |
| U-CONV-23 | with_token_roundtrip | `split_item_name(with_token("Olivo", t))` | `("Olivo", t)` | FR-10 |
| U-CONV-24 | slug_accents | `slug("Manutenzione perché", "entry")` | `"manutenzione-perche"` | FR-38 |
| U-CONV-25 | slug_table_letters | `"Straße"`, `"Œuvre"`, `"Ølstue"`, `"Łódź"` | `"strasse"`, `"oeuvre"`, `"olstue"`, `"lodz"` | FR-38 |
| U-CONV-26 | slug_fallback | `slug("★★★", "entry")`, `slug("★★★", "file")` | `"entry"`, `"file"` | FR-38, EC-10 |
| U-CONV-27 | unique_slug_collision | `unique_slug` for `"Care/1"` then `"Care 1"` then `"Care 1"` in one set | `"care-1"`, `"care-1-2"`, `"care-1-3"` | FR-38, EC-9 |

### 2.2 formats.py

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-FMT-01 | lookup_every_extension | each of `.pdf .jpg .jpeg .png .webp .mp3 .m4a .mp4 .url .webloc` | kind and content type exactly as the FR-7 table | FR-7 |
| U-FMT-02 | lookup_uppercase | `"MENU.PDF"`, `"clip.MP4"` | document/`application/pdf`, video/`video/mp4`; `extension` lowercase | FR-7, EC-16 |
| U-FMT-03 | lookup_unknown | `"notes.docx"`, `"archive"` | None | FR-7, FR-9 |
| U-FMT-04 | link_url_crlf | `b"[InternetShortcut]\r\nURL=https://example.com/a\r\n"` as `x.url` | `"https://example.com/a"` | FR-8 |
| U-FMT-05 | link_url_bom | UTF-8 BOM + INI body | the URL | FR-8 |
| U-FMT-06 | link_webloc_xml | `plistlib.dumps({"URL": u}, fmt=FMT_XML)` | `u` | FR-8 |
| U-FMT-07 | link_webloc_binary | `plistlib.dumps({"URL": u}, fmt=FMT_BINARY)` | `u` | FR-8, EC-13 |
| U-FMT-08 | link_rejects_javascript | `URL=javascript:alert(1)` | None | FR-8, EC-12 |
| U-FMT-09 | link_rejects_data | webloc with `data:text/html,x` | None | FR-8, EC-12 |
| U-FMT-10 | link_rejects_file | `URL=file:///etc/passwd` | None | FR-8, EC-12 |
| U-FMT-11 | link_rejects_relative | `URL=/book` | None | FR-8, EC-12 |
| U-FMT-12 | link_rejects_no_section | `URL=https://example.com` without section | None | FR-8 |
| U-FMT-13 | link_rejects_garbage_plist | `b"\x00\x01not a plist"` as `.webloc` | None | FR-8 |
| U-FMT-14 | link_size_cap | body of `MAX_LINK_BYTES + 1` bytes | None | FR-8, EC-14 |

### 2.3 theme.py and i18n.py

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-THM-01 | default_theme | `from_json(b"")` and `from_json(b"{not json")` | `DEFAULT_THEME`, one WARNING logged for the invalid body | FR-15, EC-20 |
| U-THM-02 | full_theme | JSON of the restaurant `theme.yaml` | every field set as in the file | FR-12 |
| U-THM-03 | bad_colour_falls_back | `colors.primary = "red"` | default primary, WARNING logged | FR-12 |
| U-THM-04 | bad_timezone_falls_back | `timezone = "Mars/Olympus"` | `timezone == "UTC"`, WARNING logged | EC-21 |
| U-THM-05 | string_override | `strings.updated = "Menu aggiornato il"`, locale `it` | `theme.string("updated") == "Menu aggiornato il"` | FR-14 |
| U-THM-06 | string_builtin | locale `it`, no overrides | `theme.string("empty") == "Qui non c'è ancora nulla."` | FR-14 |
| U-THM-07 | dark_only_when_given | custom theme without `colors_dark` | `colors_dark is None`; with it, set | A-10 |
| U-I18N-01 | every_key_every_locale | `STRINGS` | the nine FR-14 keys present in `en` and `it` with the FR-14 texts | FR-14 |
| U-I18N-02 | date_it | 2026-09-25 12:30 UTC, `it`, `Europe/Rome` | `"25/09/2026 14:30"` | FR-33 |
| U-I18N-03 | date_en | same instant, `en`, `Europe/Rome` | `"25 Sep 2026, 14:30"` | FR-33 |

### 2.4 catalog.py

Fixture: prefix `source/Vivaio/Olivo · 3xk9m2p7qhv4/`, objects built with `SourceObject`.

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-CAT-01 | item_prefix_depth | keys at depth 2, 3, 4 and 5 under `source/` | prefix only for depth ≥ 3 keys (`source/C/I/...`), None otherwise | FR-1 |
| U-CAT-02 | split_prefix_nfc | NFD prefix | NFC collection and folder | FR-6 |
| U-CAT-03 | one_resource_entry_label | `10 Care sheet/care.pdf` | one button, label `"Care sheet"`, context `""`, order 10 | FR-4 |
| U-CAT-04 | many_resources_entry | `20 Photos/a.jpg`, `20 Photos/b.jpg` | two buttons labelled `"a"` and `"b"`, context `"Photos"` | FR-4 |
| U-CAT-05 | order_across_entries | entries `20 B`, `10 A`, `C` | buttons A, B, C | FR-5 |
| U-CAT-06 | file_in_item_root | `readme.pdf` directly in the item | no button, anomaly `file in item root` | FR-9 |
| U-CAT-07 | too_deep | `10 A/sub/x.pdf` | no button, anomaly `deeper than entry level` | FR-9 |
| U-CAT-08 | unknown_extension | `10 A/x.docx` | no button, anomaly `format not accepted` | FR-9 |
| U-CAT-09 | folder_placeholder | key ending with `/` | ignored, no anomaly | FR-9 |
| U-CAT-10 | ignored_names_silent | `10 A/.DS_Store`, `_draft/x.pdf` | no button, no anomaly | FR-9, EC-11 |
| U-CAT-11 | mixed_entry | `10 A/x.pdf` and `10 A/y.docx` | one button (x), one anomaly (y) | EC-17 |
| U-CAT-12 | nfc_nfd_single_button | `10 Menù/a.pdf` in NFC and NFD | one button | EC-8 |
| U-CAT-13 | public_path_lowercase_ext | `10 Clip/Pruning.MP4` | `public_key` ends with `/clip/pruning.mp4`, content type `video/mp4` | EC-16, FR-38 |
| U-CAT-14 | slug_collision_entries | entries `Care/1` style names producing the same slug | distinct paths `care-1/`, `care-1-2/` | EC-9 |
| U-CAT-15 | too_large_resource | object with `size = 5 GiB + 1` | no button, anomaly `too large for single copy` | EC-15 |
| U-CAT-16 | link_button | `50 Book/book.url` with valid body in `link_bodies` | button kind `link`, `href` the URL, `public_key` None | FR-8, FR-32 |
| U-CAT-17 | invalid_link_anomaly | `.url` body with `javascript:` | no button, anomaly `invalid link` | FR-8, EC-12 |
| U-CAT-18 | links_not_published | item with one pdf and one url | `published_keys` = index, qr, pdf only | FR-8 |
| U-CAT-19 | only_invalid_links_is_empty | item with only invalid links | `item.empty` True | EC-18 |
| U-CAT-20 | updated_at_max_including_links | modified 1 Sep (pdf), 5 Sep (url) | `updated_at` = 5 Sep | FR-27 |
| U-CAT-21 | untokenised_item | prefix without token | `item.token == ""`, label = folder name | FR-3 |

### 2.5 render.py and qr.py

Fixture: an item with ten buttons, two per kind, labels of 55 characters with context.

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-RND-01 | no_script | `render_page(item, theme)` | no `<script` in output | FR-30 |
| U-RND-02 | one_style_block | same | exactly one `<style>` | FR-30 |
| U-RND-03 | weight_ten_buttons | same | `len(output.encode()) < 15360` | FR-30 |
| U-RND-04 | no_remote_resources | same | no `http://` or `https://` in `src=`/`href=` except link buttons; logo `src="/_assets/logo.svg"` | FR-30, FR-13 |
| U-RND-05 | order_of_sections | theme with notice, logo, header, footer | substrings appear in order: notice, logo, header, `<h1>`, subtitle, `<ul>`, footer, updated line | FR-31 |
| U-RND-06 | subtitle_rule | header set vs not set | collection subtitle present only when header is set | FR-31 |
| U-RND-07 | derived_tones_only | CSS in output | every `color-mix(` argument references only `--t`, `--bg`, `--p`; no `#fff`/`#000` in it | FR-31, T-14 |
| U-RND-08 | dark_block_rule | custom theme without and with `colors_dark`; default theme | `prefers-color-scheme:dark` absent, present, present | A-10 |
| U-RND-09 | file_href_absolute | document button | `href="/{token}/{entry}/{file}.pdf"` | FR-32 |
| U-RND-10 | link_rel | link button | external `href` and `rel="noopener noreferrer"`, no `target` | FR-32, A-11 |
| U-RND-11 | icon_accessible_name | one button per kind, locale `it` | `aria-label` values `Documento`, `Immagine`, `Audio`, `Video`, `Link` | FR-14, FR-32 |
| U-RND-12 | escaping | label `<b>&"'</b>`, footer `"a & b"`, link URL with `"` | escaped entities, no raw `<b>` in output | FR-34 |
| U-RND-13 | updated_line | `updated_at` 2026-09-25 12:30 UTC, `it`, `Europe/Rome` | contains `Aggiornato il 25/09/2026 14:30` | FR-33 |
| U-RND-14 | empty_item | item without buttons | `strings.empty` text, no `<ul>` | FR-9 |
| U-RND-15 | robots_noindex | any page | `<meta name=robots content=noindex,nofollow>` | 10.8 |
| U-RND-16 | not_found_page | `render_not_found(theme)`, locale `en` | `Page not available` and `not_found_body`; no token, no collection name | FR-35 |
| U-QR-01 | qr_decodes | `qr_svg("https://d1.cloudfront.net/3xk9m2p7qhv4")` rendered to PNG in the test (dev dependency) | decodes to the same URL | FR-37, T-13 |
| U-QR-02 | qr_level_q | same | QR built with error correction Q (inspect `QRCode.error_correction`) | FR-37 |

### 2.6 publish.py (stub clients)

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-PUB-01 | settings_required | env without `BUCKET` | `RuntimeError` naming `BUCKET` | 10.4 |
| U-PUB-02 | settings_prefix_normalised | `SOURCE_PREFIX="/source//"` | `"source/"` | 10.4 |
| U-PUB-03 | listing_paginated | 2,500 objects, stub page size 1,000 | 2,500 `SourceObject`s | EC-35 |
| U-PUB-04 | first_publication | untokenised folder with one pdf | objects moved to `… · {token_for(...)}/`, old keys deleted, `public/{token}/index.html`, `qr.svg`, the pdf copied | FR-10, FR-20 |
| U-PUB-05 | empty_untokenised_not_christened | publish on a prefix with no objects and no token | no writes at all | EC-3 |
| U-PUB-06 | concurrent_christening_converges | two publishers on the same untokenised folder, interleaved at the copy step | a single tokenised prefix; public keys under one token | EC-2 |
| U-PUB-07 | copy_metadata | pdf and mp4 sources with `application/octet-stream` | copies with FR-7 content type, `MetadataDirective=REPLACE`, `Content-Disposition: inline; filename="…"`, `Cache-Control: public, max-age=300` | FR-36, FR-7 |
| U-PUB-08 | ascii_filename | source file `Menù d'estate.pdf` | `filename="Menu d'estate.pdf"` transliterated; a name that becomes empty gives `filename="file.pdf"` | FR-36 |
| U-PUB-09 | copy_skipped_same_etag | republish with identical source | zero `copy_object` calls | FR-23 |
| U-PUB-10 | replacement | change the pdf body and set its `LastModified` one day later, republish | exactly one `copy_object`, exactly one `put_object` of `index.html` (the date line changed), one invalidation `/{token}*` | FR-21 |
| U-PUB-11 | removal | delete one of two pdfs, republish | its public key deleted, page has one button | FR-22 |
| U-PUB-12 | idempotent_page | publish twice, no change | second run: zero `put_object`, zero `copy_object`, page bytes identical | FR-23 |
| U-PUB-13 | page_date_from_source | stub clock set to 2030, resources modified 2026-09-01 | page shows 01/09/2026 | FR-27 |
| U-PUB-14 | rename_keeps_publication | move all objects from `A · t/` to `B · t/`, then publish old prefix | publication kept, page republished with label B | FR-24, EC-4 |
| U-PUB-15 | move_collection_keeps_publication | move from `C1/A · t/` to `C2/A · t/`, publish old prefix | same as U-PUB-14, owner found in C2 | EC-5 |
| U-PUB-16 | empty_removes_publication | delete all objects of a tokenised item, publish | every `public/{t}/` key deleted, invalidation issued | FR-25, EC-34 |
| U-PUB-17 | restore_same_token | recreate `C/A/x.pdf` (no token) after U-PUB-16 | christened to the same token `t` (derived) | FR-25 |
| U-PUB-18 | token_edited_new_address | rename `A · t` to `A · t2broken` (invalid tail) | christened to `token_for(C, "A · t2broken")`; old token publication removed on its empty event | EC-6 |
| U-PUB-19 | duplicate_token | `C/A · t/` and `C/B · t/` both with files | only the lexically smaller prefix published; WARNING `duplicate token` | EC-7 |
| U-PUB-20 | prune_spares_recent | a public object with `LastModified` after run start that is not in the model | not deleted | EC-28 |
| U-PUB-21 | invalidation_failure_not_raised | stub CloudFront raises | publish returns normally, WARNING logged | EC-26 |
| U-PUB-22 | theme_loaded_once | two publishes in one invocation | one `get_object` on `config/theme.json` | 10.4 |
| U-PUB-23 | theme_missing | no `config/theme.json` | page rendered with `DEFAULT_THEME` | EC-20 |
| U-PUB-24 | error_page | `publish_error_page()` | `public/404.html` with the themed not-found page, `text/html; charset=utf-8` | FR-35 |
| U-PUB-25 | republish_all_enqueues | 23 items in 3 collections | 3 `send_message_batch` calls (10+10+3), bodies parse back to the 23 prefixes; returns 23 | 10.5, FR-15 |
| U-PUB-26 | republish_all_invalidates | same | one invalidation containing `/404.html` and `/_assets/*` | 10.5 |
| U-PUB-28 | existing_token_kept | folder `C/A · k7m2p9x4qzbv/` whose token is not `token_for(C, A)` | no rename; published under `k7m2p9x4qzbv` | FR-11, A-8 |
| U-PUB-29 | republish_interleaved_with_event | a republish-all message and an S3 event for the same item processed in the same batch and then in two overlapping runs (stub interleaving at the copy step) | final public keys and page bytes identical to a single publish; no key of the item deleted by the second run | EC-19, EC-28 |
| U-PUB-27 | only_publisher_writes_public | any scenario above | no write outside `public/` except christening moves inside `source/` | EC-27 |

### 2.7 handler.py

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-HDL-01 | decode_keys | body with key `source/Vivaio/Olivo+%C2%B7+3xk9m2p7qhv4/10+A/x.pdf` | publish called with prefix `source/Vivaio/Olivo · 3xk9m2p7qhv4/` | EC-25 |
| U-HDL-02 | dedup_prefixes | 10 records of one item in one batch | publish called once | EC-1 |
| U-HDL-03 | test_event_skipped | body `{"Event":"s3:TestEvent"}` | no publish, empty `batchItemFailures` | EC-23 |
| U-HDL-04 | garbage_skipped | body `not json` | no publish, empty `batchItemFailures` | EC-24 |
| U-HDL-05 | partial_failure | two items, the stub makes one raise | `batchItemFailures` lists only the failing item's message ids | FR-26 |
| U-HDL-06 | direct_republish | event `{"action":"republish_all"}` | error page published, `republish_all` called, returns `{"items": n}` | 10.5 |
| U-HDL-07 | logging_level | root logger with an existing handler, `LOG_LEVEL=INFO` | root level INFO after import | trap `logging.basicConfig` |
| U-HDL-08 | out_of_convention_key | key `source/readme.pdf` | no publish, WARNING logged | FR-9 |

### 2.8 Repository-level tests

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| U-REPO-01 | examples_have_tokens | every item folder under `examples/*/content/*/` | `split_item_name` returns a valid token for each | FR-43, US-23 |
| U-REPO-02 | examples_formats_valid | every file under `examples/*/content/` | `lookup` not None or ignored name; every `.url`/`.webloc` parses | FR-7, FR-8 |
| U-REPO-03 | examples_media_budget | every media file in examples | size < 102,400 bytes | 10.11, T-23 |
| U-REPO-04 | name_only_in_allowed_places | files under `src/` | the literal project name appears only in `src/swingtag/__init__.py` | SPEC 10.2 naming rule |
| U-REPO-05 | examples_contrast | each example `theme.yaml` | text/background ≥ 4.5 and primary/background ≥ 3 (same formula as T-10) | T-22 |
| U-PLT-01 | pdfmin_valid | `make_pdf_pages` with 2 pages | starts with `%PDF-`, ends with `%%EOF`, xref offsets point at `obj` | FR-45 |
| U-PLT-02 | plates_grid | 20 christened items from a stub listing | 2 pages, 18 cells on page 1, each with label and collection; untokenised items skipped | FR-45 |

## 3. Terraform tests (`terraform test`, mocked provider)

| ID | Name | Input | Expected | Covers |
|---|---|---|---|---|
| TF-01 | defaults_plan | module with an example theme, no domain | plan succeeds; zero ACM, Route 53 resources | FR-44, T-46 |
| TF-02 | domain_without_zone | `domain_name` set, zone empty | `expect_failures = [var.hosted_zone_name]` | EC-32 |
| TF-03 | domain_with_zone | both set | one certificate (us-east-1 alias), validation records, A and AAAA aliases | FR-44 |
| TF-04 | bad_colour | theme with `primary: red` | precondition failure naming `colors.primary` | FR-12 |
| TF-05 | bad_locale | `locale: fr` | precondition failure naming `locale` | FR-12 |
| TF-06 | missing_logo | `logo: missing.svg` | precondition failure naming `logo` | FR-12, EC-22 |
| TF-07 | unknown_top_level_key | `colour: red` | precondition failure listing `colour` | FR-12 |
| TF-08 | unknown_string_key | `strings.updatd` | precondition failure listing `updatd` | FR-12, FR-14 |
| TF-09 | partial_dark | `colors_dark` with two keys | precondition failure | FR-12 |
| TF-10 | asset_extension | `theme/assets/logo.gif` | precondition failure naming the file | FR-13 |
| TF-11 | contrast_warning | exhibition theme with `primary: #c9a227` | plan succeeds with a check warning (`check` block assertion) | FR-31, T-09 |
| TF-12 | notifications_filtered | plan | bucket notification to the queue with `filter_prefix = "source/"` and events `s3:ObjectCreated:*`, `s3:ObjectRemoved:*` | EC-27 |
| TF-13 | no_reserved_concurrency | plan | `reserved_concurrent_executions` unset; event source mapping `maximum_concurrency = 2`, `function_response_types = ["ReportBatchItemFailures"]` | trap, FR-26 |
| TF-14 | queue_settings | plan | visibility = 6 × timeout, redrive `maxReceiveCount = 5`, alarm on DLQ visible messages > 0 | FR-26 |
| TF-15 | cloudfront_errors | plan | custom error responses 403 and 404 → `/404.html`, response code 404 | FR-35 |
| TF-16 | csp_media_src | plan | response headers policy CSP string equals SPEC 10.7, includes `media-src 'self'` | 10.7, T-11 |
| TF-17 | origin_path_public | plan | origin path `/public`, OAC attached | 10.7 |
| TF-18 | iam_no_wildcards | plan | no `"*"` in any Resource of the function policy; ListBucket conditioned on `source/` and `public/` | 10.8 |
| TF-19 | uploader_statement_optional | `uploader_principal_arns = []` vs one ARN | statement absent vs present with `source/*` only | FR-46 |
| TF-20 | theme_json_uploaded | plan | object `config/theme.json` with `jsonencode` of the theme; one object per asset at `public/_assets/` | FR-13, 10.4 |
| TF-21 | republish_triggers | plan twice with a changed asset | `aws_lambda_invocation` triggers differ | FR-15, T-44 |
| TF-22 | examples_force_destroy | each example root | bucket `force_destroy = true`; module default false | FR-42 |
| TF-23 | example_pages_output | restaurant example | `pages` has key `"Osteria Quattro Mestoli / Menu"` with a URL ending in its token | FR-43 |

## 4. Rewrite function tests (Node)

| ID | Name | Input URI | Expected URI | Covers |
|---|---|---|---|---|
| JS-01 | root | `/` | `/index.html` | EC-33 |
| JS-02 | token | `/3xk9m2p7qhv4` | `/3xk9m2p7qhv4/index.html` | EC-33 |
| JS-03 | token_slash | `/3xk9m2p7qhv4/` | `/3xk9m2p7qhv4/index.html` | EC-33 |
| JS-04 | resource | `/3xk9m2p7qhv4/care-sheet/care.pdf` | unchanged | 10.7 |
| JS-05 | assets | `/_assets/logo.svg` | unchanged | FR-13 |
| JS-06 | error_page | `/404.html` | unchanged | FR-35 |

## 5. Live tests (lab account, per example)

Preconditions: `make demo EXAMPLE=<name>` completed; `BASE` = the `base_url` output; `BUCKET`
= the `bucket` output; `T` = a token from the `pages` output. "Within 60 s" means polling
every 5 s, failing at 60 s.

| ID | Name | Procedure | Expected | Covers |
|---|---|---|---|---|
| L-01 | verify_script | `make verify EXAMPLE=<name>` | exit code 0 | FR-47 |
| L-02 | all_pages_up | `curl -s -o /dev/null -w '%{http_code}'` on every `pages` URL | all `200` | G-2, FR-41 |
| L-03 | demo_time | time `make demo` on a clean state | under 20 minutes | T-55 |
| L-04 | first_publication | `aws s3 cp x.pdf "s3://$BUCKET/source/Live/New item/10 Doc/x.pdf"` | within 60 s the folder is renamed with a token and `$BASE/{token}` answers 200 with one button | FR-20, EC-31 |
| L-05 | replacement | overwrite that pdf with different bytes | within 60 s `curl $BASE/{token}/doc/x.pdf \| md5` equals the new file | FR-21, T-37 |
| L-06 | removal | delete it and add another resource | within 60 s the old resource URL answers 404 page, page shows only the new button | FR-22, EC-34 |
| L-07 | rename | `aws s3 mv --recursive` the item folder to a new label keeping ` · {token}` | within 60 s `$BASE/{token}` answers 200 with the new label | FR-24, T-53 |
| L-08 | bulk_upload | upload 10 files of one item in one `aws s3 cp --recursive` | Lambda logs show one publication for that prefix; DLQ empty | EC-1, T-36 |
| L-09 | theme_change | change `colors.primary`, `make demo` again | every page contains the new colour; one `aws_lambda_invocation` | FR-15, T-44 |
| L-10 | idempotent_apply | `make demo` twice without changes | second `terraform apply` prints `No changes.`; zero new `published` log lines in the function log group during the run | EC-29 |
| L-11 | console_edit_restored | change a mock in the bucket, run apply | object restored, page back to the committed content | EC-30 |
| L-12 | source_unreachable | `curl $BASE/source/…`, `$BASE/config/theme.json`, `%2e%2e` variants | 404 page for all | 10.7, T-38 |
| L-13 | forbidden_is_404 | request a key that exists only under `source/` via its public-looking path | status 404, themed body | FR-35, T-39 |
| L-14 | range_mp4 | `curl -r 0-99 -D - $BASE/{token}/…/clip.mp4` | `206`, `Accept-Ranges: bytes`, 100 bytes | FR-47, T-42 |
| L-15 | headers_everywhere | `curl -I` on a page, an mp4, the 404 | the five SPEC 10.7 headers on all three | T-41 |
| L-16 | dlq_alarm | temporarily break the function (bad env), upload | after 5 receives the message is in the DLQ and the alarm is in ALARM | FR-26, T-54 |
| L-17 | teardown | `make destroy EXAMPLE=<name>` | bucket and distribution gone; `aws s3api head-bucket` fails | FR-42, T-47 |
| L-19 | demo_from_clean_clone | fresh `git clone`, Terraform 1.9.x, Python 3.12, lab credentials, `make demo EXAMPLE=restaurant` | the output shows pytest, then the package build, then `Apply complete!` and the `pages` map, in this order; exit code 0 | FR-40 |
| L-20 | terraform_version_floor | same with Terraform 1.8.x | `terraform init` fails with the `required_version` message | FR-40, T-21 |
| L-18 | origin_reruns | the ORIGIN entries of ASSUMPTIONS (T-33, T-35, T-36, T-39, T-43, T-50, T-51, T-52, T-53) re-run as their backlog issues describe | each recorded CONFIRMED | ASSUMPTIONS |

## 6. Device tests

| ID | Name | Procedure | Expected | Covers |
|---|---|---|---|---|
| D-01 | ios_media | iPhone, Safari: open the exhibition audio and video buttons | both play, seek works | T-60 |
| D-02 | ios_render | iPhone, Safari: open one page per example, light mode | no horizontal scroll (page width = viewport width); buttons at least 56 px high (Web Inspector); colours match the theme hex values; screenshot recorded | T-61 |
| D-03 | android_all_kinds | Android, Chrome: tap one button per kind | each resource is displayed or played within 5 s of the tap, inline or in a system app; record which, per kind | T-62 |
| D-04 | plates_scan | print the nursery plates sheet at 100 %, scan each code with the camera app | every code opens its page | T-63, FR-45 |
| D-05 | readme_minute | a person who has not seen the project reads the README for 60 s, then answers "what does it do?" | the answer mentions all three of: a QR on a physical object, a page per object, files in a folder (S3) | G-1, FR-50 |

## 7. Ambiguities found while writing this plan

Following the method (restate, list assumptions, flag ambiguities), these are the points
where SPEC 1.0 allowed more than one reading. Each has a proposed resolution; none is applied
to the spec until the owner confirms.

| ID | Where | Ambiguity | Proposed resolution |
|---|---|---|---|
| AMB-1 | FR-20..FR-22 "within one minute" | measured from what to what | from the S3 `PutObject`/`DeleteObject` response to the first CloudFront response reflecting it (L-04..L-06 measure exactly this) |
| AMB-2 | FR-31 "WCAG AA contrast … warning" vs examples | whether the examples may ship with a warning | examples must produce no contrast warning (U-REPO-05, TF-11 uses a deliberately bad theme) |
| AMB-3 | EC-7 duplicate token, "lexical key order" | byte order or casefold order | byte order of the NFC-normalised prefix, as Python `sorted()` on `str` |
| AMB-4 | FR-9 anomaly wording | exact log strings are asserted by tests | the reasons are the fixed strings used in U-CAT-06..08, 15, 17 and U-PUB-19: `file in item root`, `deeper than entry level`, `format not accepted`, `too large for single copy`, `invalid link`, `duplicate token` |
| AMB-5 | FR-36 ASCII filename fallback | fallback name when transliteration leaves nothing | `file{ext}` (e.g. `file.pdf`), as in U-PUB-08 |

## 8. Coverage

Every functional requirement and edge case of SPEC 1.0 appears in at least one test above.
Check: `python3 spec/check_coverage.py` lists any FR-n or EC-n present in `SPEC.md` and absent
from this file; it must print nothing.
