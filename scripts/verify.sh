#!/usr/bin/env bash
# Live verification of a deployment. Usage: scripts/verify.sh <base-url> <token>
# Exit code = number of failed checks. Bash 3.2 compatible (macOS): no apostrophes inside
# expansions.
set -uo pipefail
if [[ $# -lt 2 ]]; then
  echo "usage: $0 <base-url> <token>" >&2
  exit 2
fi
base="${1%/}"
token="$2"
failed=0

check() { # description, expected substring, actual
  if [[ "$3" == *"$2"* ]]; then
    printf 'ok    %s\n' "$1"
  else
    printf 'FAIL  %s (expected "%s", got "%s")\n' "$1" "$2" "$(printf '%s' "$3" | head -c 160)"
    failed=$((failed + 1))
  fi
}

lower() { tr 'A-Z' 'a-z'; }

page_headers="$(curl -sS -D - -o /dev/null "$base/$token" | lower)"
check "short URL served" " 200" "$(printf '%s' "$page_headers" | head -1)"
for header in "strict-transport-security" "x-content-type-options: nosniff" "x-frame-options: deny" \
  "referrer-policy: no-referrer" "content-security-policy"; do
  check "header $header" "$header" "$page_headers"
done
check "CSP allows same-origin media" "media-src 'self'" "$page_headers"

host="${base#https://}"
check "HTTP redirects to HTTPS" "301" "$(curl -sS -o /dev/null -w '%{http_code}' "http://$host/$token")"

page="$(curl -sS "$base/$token")"
[[ "$page" == *"<script"* ]] && { echo "FAIL  page contains <script>"; failed=$((failed + 1)); }

missing="$(curl -sS -o /dev/null -w '%{http_code}' "$base/zzzzzzzzzzzz")"
check "unknown token answers 404" "404" "$missing"
check "404 page body" "<h1>" "$(curl -sS "$base/zzzzzzzzzzzz")"
check "dot segments rejected at the edge" "400" "$(curl -sS -o /dev/null -w '%{http_code}' --path-as-is "$base/$token/../../config/theme.json")"

hrefs="$(printf '%s' "$page" | grep -o "href=\"/$token/[^\"]*\"" | sed 's/^href="//; s/"$//')"
[[ -z "$hrefs" ]] && echo "skip  no file resources on this page: type and disposition checks not run"
printf '%s' "$hrefs" | grep -q '\.mp4$' || echo "skip  no mp4 on this page: range checks not run (try the nursery or exhibition)"
for href in $hrefs; do
  ext="${href##*.}"
  headers="$(curl -sS -I "$base$href" | lower)"
  case "$ext" in
    pdf) expected="application/pdf" ;;
    jpg | jpeg) expected="image/jpeg" ;;
    png) expected="image/png" ;;
    webp) expected="image/webp" ;;
    mp3) expected="audio/mpeg" ;;
    m4a) expected="audio/mp4" ;;
    mp4) expected="video/mp4" ;;
    *) expected="?" ;;
  esac
  check "type of $href" "content-type: $expected" "$headers"
  check "inline disposition of $href" "content-disposition: inline" "$headers"
  if [[ "$ext" == "mp4" ]]; then
    check "HEAD advertises ranges for $href" "accept-ranges: bytes" "$headers"
    ranged="$(curl -sS -D - -o /dev/null -r 0-99 "$base$href" | lower)"
    check "range request answers 206" " 206" "$(printf '%s' "$ranged" | head -1)"
    check "range request has content-range" "content-range: bytes 0-99/" "$ranged"
  fi
done

check "QR code served" "200" "$(curl -sS -o /dev/null -w '%{http_code}' "$base/$token/qr.svg")"
echo "$failed failed check(s)"
exit "$failed"
