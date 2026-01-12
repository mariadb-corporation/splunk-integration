#!/bin/bash
#
# SkySQL Logs API Wrapper Script
# Sets environment variables and executes the Python input script
#

# SkySQL API Configuration
export SKYSQL_API_KEY="your-api-key-here"
export SKYSQL_API_URL="https://api.skysql.com"
export CHECKPOINT_FILE="/opt/splunkforwarder/var/lib/splunk/skysql_checkpoint.json"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Execute the Python script using Splunk's Python
/opt/splunkforwarder/bin/splunk cmd python3 "${SCRIPT_DIR}/skysql_logs_input.py"
