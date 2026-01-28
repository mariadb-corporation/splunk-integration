#!/bin/bash
#
# Example: Cron Job Configuration for MariaDB Cloud Metrics
# 
# NOTE: Daemon mode is now the RECOMMENDED approach for continuous metrics collection.
# This cron example is kept for backward compatibility and simple use cases.
# For production, consider using daemon mode with systemd/launchd instead.
#

echo "=== Cron Job Example (Legacy) ==="
echo "NOTE: Daemon mode is recommended for production use"
echo "This would be added to crontab with:"
echo ""
echo "# Run every 1 minute"
echo "*/1 * * * * export MARIADB_API_KEY='your-mariadb-api-key' && export MARIADB_API_URL='https://api.skysql.com' && export SPLUNK_HEC_TOKEN='your-splunk-hec-token' && export SPLUNK_HEC_VERIFY_SSL='true' && /path/to/splunk-integration/metrics/scripts/mariadb_metrics_wrapper.sh >> /var/log/mariadb_metrics_cron.log 2>&1"
echo ""
echo "To install:"
echo "  crontab -e"
echo "  # Add the line above with your actual credentials"
echo "  # Save and exit"
echo ""
echo "To verify:"
echo "  crontab -l"
echo ""
echo "To check logs:"
echo "  tail -f /var/log/mariadb_metrics_cron.log"
echo ""
echo "Simulating cron execution now..."
echo ""

# Simulate cron execution
export MARIADB_API_KEY='your-mariadb-api-key'
export MARIADB_API_URL='https://api.skysql.com'
export SPLUNK_HEC_TOKEN='your-splunk-hec-token'
export SPLUNK_HEC_VERIFY_SSL='true'

# Update this path to your actual installation directory
SCRIPT_DIR="/path/to/splunk-integration"
$SCRIPT_DIR/metrics/scripts/mariadb_metrics_wrapper.sh

echo ""
echo "=== Cron Job Test Complete ==="
