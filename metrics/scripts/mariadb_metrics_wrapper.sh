#!/bin/bash
#
# MariaDB Cloud Metrics API Wrapper Script
# Sets environment variables and executes the Python metrics collection script
#

# Exit on error
set -e

# MariaDB Cloud API Configuration
export MARIADB_API_KEY="${MARIADB_API_KEY:-your-api-key-here}"
export MARIADB_API_URL="${MARIADB_API_URL:-https://api.skysql.com}"

# Splunk Cloud Platform HEC Configuration
export SPLUNK_HEC_URL="${SPLUNK_HEC_URL:-https://inputs.prd-p-29k1h.splunkcloud.com:8088}"
export SPLUNK_HEC_TOKEN="${SPLUNK_HEC_TOKEN:-your-hec-token-here}"
export SPLUNK_INDEX="${SPLUNK_INDEX:-main}"
export SPLUNK_SOURCE="${SPLUNK_SOURCE:-mariadbl_metrics_api}"
export SPLUNK_SOURCETYPE="${SPLUNK_SOURCETYPE:-metrics}"

# Metrics Collection Configuration
export METRICS_CHECKPOINT_FILE="${METRICS_CHECKPOINT_FILE:-/var/lib/mariadb/metrics_checkpoint.json}"
export METRICS_POLL_INTERVAL="${METRICS_POLL_INTERVAL:-60}"
export METRICS_BATCH_SIZE="${METRICS_BATCH_SIZE:-100}"
export METRICS_MAX_RETRIES="${METRICS_MAX_RETRIES:-3}"
export METRICS_RETRY_DELAY="${METRICS_RETRY_DELAY:-5}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Determine Python executable
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python 3 is required but not found in PATH" >&2
    exit 1
fi

# Check if running with Splunk's Python (if available)
if [ -f "/opt/splunkforwarder/bin/splunk" ]; then
    echo "INFO: Detected Splunk Universal Forwarder, using Splunk's Python"
    PYTHON_CMD="/opt/splunkforwarder/bin/splunk cmd python3"
fi

# Validate required environment variables
if [ "${MARIADB_API_KEY}" = "your-api-key-here" ]; then
    echo "ERROR: MARIADB_API_KEY must be set" >&2
    exit 1
fi

if [ "${SPLUNK_HEC_TOKEN}" = "your-hec-token-here" ]; then
    echo "ERROR: SPLUNK_HEC_TOKEN must be set" >&2
    exit 1
fi

# Create checkpoint directory if it doesn't exist
CHECKPOINT_DIR="$(dirname "${METRICS_CHECKPOINT_FILE}")"
if [ ! -d "${CHECKPOINT_DIR}" ]; then
    echo "INFO: Creating checkpoint directory: ${CHECKPOINT_DIR}"
    mkdir -p "${CHECKPOINT_DIR}" || {
        echo "WARNING: Failed to create checkpoint directory, using /tmp"
        export METRICS_CHECKPOINT_FILE="/tmp/metrics_checkpoint.json"
    }
fi

# Log execution start
echo "INFO: Starting MariaDB Cloud metrics collection at $(date)"
echo "INFO: MariaDB API URL: ${MARIADB_API_URL}"
echo "INFO: Splunk HEC URL: ${SPLUNK_HEC_URL}"
echo "INFO: Splunk Index: ${SPLUNK_INDEX}"
echo "INFO: Checkpoint file: ${METRICS_CHECKPOINT_FILE}"

# Execute the Python script
${PYTHON_CMD} "${SCRIPT_DIR}/mariadb_metrics_input.py"
EXIT_CODE=$?

# Log execution result
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "INFO: Metrics collection completed successfully at $(date)"
else
    echo "ERROR: Metrics collection failed with exit code ${EXIT_CODE} at $(date)" >&2
fi

exit ${EXIT_CODE}
