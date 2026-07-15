#!/bin/bash
#
# MariaDB Cloud Logs API Wrapper Script
# Sets environment variables and executes the Python logs collection script
# which sends logs to a Splunk HTTP Event Collector (HEC) endpoint.
#
# Note: no `set -e` — the collector's exit code is captured and reported
# explicitly below, and a non-zero exit is propagated via `exit ${EXIT_CODE}`.

# MariaDB Cloud API Configuration
export MARIADB_API_KEY="${MARIADB_API_KEY:-your-api-key-here}"
export MARIADB_API_URL="${MARIADB_API_URL:-https://api.skysql.com}"
export CHECKPOINT_FILE="${CHECKPOINT_FILE:-./mariadb_checkpoint.json}"

# Splunk Cloud Platform HEC Configuration
export SPLUNK_HEC_URL="${SPLUNK_HEC_URL:-https://inputs.your-instance.splunkcloud.com:8088}"
export SPLUNK_HEC_TOKEN="${SPLUNK_HEC_TOKEN:-your-hec-token-here}"
export SPLUNK_HEC_VERIFY_SSL="${SPLUNK_HEC_VERIFY_SSL:-true}"
export SPLUNK_INDEX="${SPLUNK_INDEX:-mariadb_logs}"
export SPLUNK_SOURCE="${SPLUNK_SOURCE:-mariadb_logs_api}"
export SPLUNK_SOURCETYPE="${SPLUNK_SOURCETYPE:-mariadb:logs}"

# Logs Collection Configuration
export LOGS_BATCH_SIZE="${LOGS_BATCH_SIZE:-100}"
export LOGS_MAX_RETRIES="${LOGS_MAX_RETRIES:-3}"
export LOGS_RETRY_DELAY="${LOGS_RETRY_DELAY:-5}"

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

# Validate required environment variables
if [ "${MARIADB_API_KEY}" = "your-api-key-here" ]; then
    echo "ERROR: MARIADB_API_KEY must be set" >&2
    exit 1
fi

if [ "${SPLUNK_HEC_TOKEN}" = "your-hec-token-here" ]; then
    echo "ERROR: SPLUNK_HEC_TOKEN must be set" >&2
    exit 1
fi

echo "INFO: Starting MariaDB Cloud logs collection at $(date)"
echo "INFO: MariaDB Cloud API URL: ${MARIADB_API_URL}"
echo "INFO: Splunk HEC URL: ${SPLUNK_HEC_URL}"
echo "INFO: Splunk Index: ${SPLUNK_INDEX}"

# Execute the Python script (pass through any CLI args, e.g. --daemon --interval)
${PYTHON_CMD} "${SCRIPT_DIR}/mariadb_logs_collector.py" "$@"
EXIT_CODE=$?

if [ ${EXIT_CODE} -eq 0 ]; then
    echo "INFO: Logs collection completed successfully at $(date)"
else
    echo "ERROR: Logs collection failed with exit code ${EXIT_CODE} at $(date)" >&2
fi

exit ${EXIT_CODE}
