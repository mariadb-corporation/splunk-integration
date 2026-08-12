#!/usr/bin/env bash
#
# Build AWS Lambda deployment packages for the MariaDB Cloud -> Splunk
# collectors.
#
# Produces two zips under deploy/lambda/dist/:
#   metrics_lambda.zip  (handler: mariadb_metrics_collector.lambda_handler)
#   logs_lambda.zip     (handler: mariadb_logs_collector.lambda_handler)
#
# Only `requests` is vendored into the package; `boto3` is intentionally NOT
# bundled because it is already present in the Lambda Python runtime.
#
# Usage:
#   deploy/lambda/build.sh              # build both packages
#   PYTHON=python3.12 deploy/lambda/build.sh
#
set -euo pipefail

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
DIST_DIR="${REPO_ROOT}/deploy/lambda/dist"
BUILD_ROOT="$(mktemp -d)"
PYTHON="${PYTHON:-python3}"

trap 'rm -rf "${BUILD_ROOT}"' EXIT

mkdir -p "${DIST_DIR}"

package() {
    local name="$1" script="$2"
    local staging="${BUILD_ROOT}/${name}"
    echo "==> Packaging ${name}"
    mkdir -p "${staging}"
    # Vendor third-party deps (requests). boto3 is excluded: the Lambda runtime
    # already provides it, and bundling it only bloats the artifact.
    "${PYTHON}" -m pip install --quiet --target "${staging}" requests
    cp "${script}" "${staging}/"
    # -X drops extra file attributes for a reproducible archive.
    ( cd "${staging}" && zip -q -r -X "${DIST_DIR}/${name}.zip" . )
    echo "    wrote ${DIST_DIR}/${name}.zip"
}

package "metrics_lambda" "${REPO_ROOT}/metrics/scripts/mariadb_metrics_collector.py"
package "logs_lambda"    "${REPO_ROOT}/logs/scripts/mariadb_logs_collector.py"

echo "Done. Deployment packages are in ${DIST_DIR}/"
