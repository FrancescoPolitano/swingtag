#!/usr/bin/env bash
# Builds the publisher package in build/lambda: the swingtag package, its only
# dependency qrcode 8.2 (pure Python, so a macOS build runs on Lambda arm64), and a
# lambda_function.py shim so Terraform never names the package.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build="${root}/build/lambda"
rm -rf "${build}" && mkdir -p "${build}"
cp -R "${root}/src/swingtag" "${build}/swingtag"
printf 'from swingtag.handler import lambda_handler  # noqa: F401\n' > "${build}/lambda_function.py"
python3 -m pip install --quiet --disable-pip-version-check --target "${build}" --only-binary :all: qrcode==8.2
rm -rf "${build}/bin"
find "${build}" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "package ready in ${build} ($(du -sh "${build}" | cut -f1))"
