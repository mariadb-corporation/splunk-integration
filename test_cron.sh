#!/bin/bash
#
# Test Cron Job Configuration for MariaDB Cloud Metrics
# This script demonstrates how to set up a cron job
#

echo "=== Cron Job Test ==="
echo "This would be added to crontab with:"
echo ""
echo "# Run every 1 minute"
echo "*/1 * * * * export MARIADB_API_KEY='skysql.1zzz.5yw3vcv6.AyTAlj9iYSsRKqW4iJgw2bCwsOZ0TADfbtza.ed3b35ed' && export MARIADB_API_URL='https://api-test.skysql.com' && export SPLUNK_HEC_TOKEN='a101e96c-88af-488f-bab6-8a5d154b3471' && export SPLUNK_HEC_VERIFY_SSL='false' && /Users/nedyalko.petrov/Documents/SkySQL/skyrepos/splunk-integration/scripts/mariadb_metrics_wrapper.sh >> /tmp/mariadb_metrics_cron.log 2>&1"
echo ""
echo "To install:"
echo "  crontab -e"
echo "  # Add the line above"
echo "  # Save and exit"
echo ""
echo "To verify:"
echo "  crontab -l"
echo ""
echo "To check logs:"
echo "  tail -f /tmp/mariadb_metrics_cron.log"
echo ""
echo "Simulating cron execution now..."
echo ""

# Simulate cron execution
export MARIADB_API_KEY='skysql.1zzz.5yw3vcv6.AyTAlj9iYSsRKqW4iJgw2bCwsOZ0TADfbtza.ed3b35ed'
export MARIADB_API_URL='https://api-test.skysql.com'
export SPLUNK_HEC_TOKEN='a101e96c-88af-488f-bab6-8a5d154b3471'
export SPLUNK_HEC_VERIFY_SSL='false'

/Users/nedyalko.petrov/Documents/SkySQL/skyrepos/splunk-integration/scripts/mariadb_metrics_wrapper.sh

echo ""
echo "=== Cron Job Test Complete ==="
