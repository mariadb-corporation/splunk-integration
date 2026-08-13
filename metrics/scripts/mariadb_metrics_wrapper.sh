#!/bin/bash
#
# MariaDB Cloud Metrics API Wrapper Script
# Sets environment variables and executes the Python metrics collection script
# which sends metrics to a Splunk HTTP Event Collector (HEC) endpoint.
#
# Note: no `set -e` — the collector's exit code is captured and reported
# explicitly below, and a non-zero exit is propagated via `exit ${EXIT_CODE}`.

# MariaDB Cloud API Configuration
export MARIADB_API_KEY="${MARIADB_API_KEY:-your-api-key-here}"
export MARIADB_API_URL="${MARIADB_API_URL:-https://api.skysql.com}"

# Splunk Cloud Platform HEC Configuration
export SPLUNK_HEC_URL="${SPLUNK_HEC_URL:-https://inputs.your-instance.splunkcloud.com:8088}"
export SPLUNK_HEC_TOKEN="${SPLUNK_HEC_TOKEN:-your-hec-token-here}"
export SPLUNK_HEC_VERIFY_SSL="${SPLUNK_HEC_VERIFY_SSL:-true}"
export SPLUNK_INDEX="${SPLUNK_INDEX:-mariadb_metrics}"
export SPLUNK_SOURCE="${SPLUNK_SOURCE:-mariadbl_metrics_api}"
export SPLUNK_SOURCETYPE="${SPLUNK_SOURCETYPE:-metrics}"

# Metrics Collection Configuration
export METRICS_BATCH_SIZE="${METRICS_BATCH_SIZE:-1000}"
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

# Validate required environment variables
if [ "${MARIADB_API_KEY}" = "your-api-key-here" ]; then
    echo "ERROR: MARIADB_API_KEY must be set" >&2
    exit 1
fi

if [ "${SPLUNK_HEC_TOKEN}" = "your-hec-token-here" ]; then
    echo "ERROR: SPLUNK_HEC_TOKEN must be set" >&2
    exit 1
fi

if [ "${SPLUNK_HEC_URL}" = "https://inputs.your-instance.splunkcloud.com:8088" ]; then
    echo "ERROR: SPLUNK_HEC_URL must be set" >&2
    exit 1
fi

# Print configuration start
echo "INFO: Starting MariaDB Cloud metrics collection at $(date)"
echo "INFO: MariaDB API URL: ${MARIADB_API_URL}"
echo "INFO: Splunk HEC URL: ${SPLUNK_HEC_URL}"
echo "INFO: Splunk Index: ${SPLUNK_INDEX}"

# Execute the Python script (pass through any CLI args, e.g. --daemon --interval)
${PYTHON_CMD} "${SCRIPT_DIR}/mariadb_metrics_collector.py" "$@"
EXIT_CODE=$?

# Log execution result
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "INFO: Metrics collection completed successfully at $(date)"
else
    echo "ERROR: Metrics collection failed with exit code ${EXIT_CODE} at $(date)" >&2
fi

exit ${EXIT_CODE}
