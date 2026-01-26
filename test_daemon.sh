#!/bin/bash
# Quick test of daemon mode - runs for 12 seconds (2 cycles with 5 second interval)

export MARIADB_API_KEY='skysql.1zzz.5yw3vcv6.AyTAlj9iYSsRKqW4iJgw2bCwsOZ0TADfbtza.ed3b35ed'
export MARIADB_API_URL='https://api-test.skysql.com'
export SPLUNK_HEC_TOKEN='a101e96c-88af-488f-bab6-8a5d154b3471'
export SPLUNK_HEC_URL='https://inputs.prd-p-29k1h.splunkcloud.com:8088'
export SPLUNK_HEC_VERIFY_SSL='false'

echo "Starting daemon mode test (will run 2 cycles with 5 second interval)..."
echo "Press Ctrl+C after ~12 seconds to test graceful shutdown"
echo ""

python3 metrics/scripts/mariadb_metrics_input.py --daemon --interval 5
