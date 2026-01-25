#!/bin/bash
#
# Example: Cron Job Configuration for MariaDB Cloud Metrics
# This script demonstrates how to set up a cron job
#

echo "=== Cron Job Example ==="
echo "This would be added to crontab with:"
echo ""
echo "# Run every 1 minute"
echo "*/1 * * * * export MARIADB_API_KEY='your-mariadb-api-key' && export MARIADB_API_URL='https://api.skysql.com' && export SPLUNK_HEC_TOKEN='your-splunk-hec-token' && export SPLUNK_HEC_VERIFY_SSL='true' && /path/to/splunk-integration/scripts/mariadb_metrics_wrapper.sh >> /var/log/mariadb_metrics_cron.log 2>&1"
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
$SCRIPT_DIR/scripts/mariadb_metrics_wrapper.sh

echo ""
echo "=== Cron Job Test Complete ==="
