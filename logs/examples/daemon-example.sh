#!/bin/bash
#
# Example: Daemon Mode for MariaDB Cloud Logs (RECOMMENDED)
# This script demonstrates running the logs collector as a continuous daemon
# that sends logs to Splunk Cloud via HEC.
#

echo "=== Daemon Mode Example (Recommended) ==="
echo ""
echo "Daemon mode runs continuously and polls the MariaDB Cloud Logs API at regular"
echo "intervals, sending log lines to Splunk Cloud via HEC."
echo ""

# MariaDB Cloud API configuration
export MARIADB_API_KEY='your-mariadb-api-key'
export MARIADB_API_URL='https://api.skysql.com'
export CHECKPOINT_FILE='/var/lib/mariadb-logs/mariadb_checkpoint.json'

# Splunk HEC configuration
export SPLUNK_HEC_TOKEN='your-splunk-hec-token'
export SPLUNK_HEC_URL='https://inputs.your-instance.splunkcloud.com:8088'
export SPLUNK_HEC_VERIFY_SSL='true'
export SPLUNK_INDEX='mariadb_logs'
export SPLUNK_SOURCETYPE='mariadb:logs'

# Update this path to your actual installation directory
SCRIPT_DIR="/path/to/splunk-integration"

echo "Starting daemon with 300 second interval..."
echo "Press Ctrl+C to stop gracefully"
echo ""

# Run in daemon mode with 5 minute interval
python3 $SCRIPT_DIR/logs/scripts/mariadb_logs_collector.py --daemon --interval 300

echo ""
echo "=== Daemon Mode Test Complete ==="
echo ""
echo "For production deployment, use:"
echo "  - systemd service (Linux): See systemd-example.service"
echo "  - launchd (macOS): See launchd-example.plist"
echo "  - Kubernetes Deployment: See kubernetes-deployment-example.yaml"
