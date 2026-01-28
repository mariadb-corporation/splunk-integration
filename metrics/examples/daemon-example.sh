#!/bin/bash
#
# Example: Daemon Mode for MariaDB Cloud Metrics (RECOMMENDED)
# This script demonstrates running the metrics collector as a continuous daemon
#

echo "=== Daemon Mode Example (Recommended) ==="
echo ""
echo "Daemon mode runs continuously and polls metrics at regular intervals."
echo "This is more efficient than cron jobs for continuous monitoring."
echo ""

# Set environment variables
export MARIADB_API_KEY='your-mariadb-api-key'
export MARIADB_API_URL='https://api.skysql.com'
export SPLUNK_HEC_TOKEN='your-splunk-hec-token'
export SPLUNK_HEC_URL='https://inputs.your-instance.splunkcloud.com:8088'
export SPLUNK_HEC_VERIFY_SSL='true'

# Update this path to your actual installation directory
SCRIPT_DIR="/path/to/splunk-integration"

echo "Starting daemon with 60 second interval..."
echo "Press Ctrl+C to stop gracefully"
echo ""

# Run in daemon mode with 60 second interval
python3 $SCRIPT_DIR/metrics/scripts/mariadb_metrics_input.py --daemon --interval 60

echo ""
echo "=== Daemon Mode Test Complete ==="
echo ""
echo "For production deployment, use:"
echo "  - systemd service (Linux): See systemd-example.service"
echo "  - launchd (macOS): See launchd-example.plist"
echo "  - Kubernetes Deployment: See kubernetes-deployment-example.yaml"
