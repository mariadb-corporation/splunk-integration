# Metrics Integration Test Checklist

This checklist guides you through testing the MariaDB Cloud metrics integration with Splunk Cloud Platform.

## Prerequisites Verification

- [ ] Python 3.7+ installed
- [ ] `requests` library installed (`pip3 install requests`)
- [ ] MariaDB Cloud API key available
- [ ] Splunk Cloud **Metrics-type** index created (e.g. `mariadb_metrics`) — not an Events/log index
- [ ] Splunk Cloud HEC token created with write access to that metrics index
- [ ] Network connectivity to both APIs

## Test 1: Verify Python Dependencies

```bash
python3 --version
python3 -c "import requests; print(f'requests {requests.__version__}')"
```

**Expected:** Python 3.7+ and requests library version displayed

## Test 2: Test MariaDB Cloud API Connectivity

```bash
# Replace with your actual API key
curl -H "X-Api-Key: YOUR_MARIADB_API_KEY" \
     https://api.skysql.com/observability/v2/metrics

# Expected: Prometheus format metrics output
```

**Expected:** Text output in Prometheus format with metrics like `mariadb_global_status_threads_connected`

## Test 3: Test Splunk HEC Connectivity

```bash
# Replace with your actual HEC token
curl -k https://inputs.your-instance.splunkcloud.com:8088/services/collector \
     -H "Authorization: Splunk YOUR_HEC_TOKEN" \
     -d '{"event":"test","sourcetype":"manual","source":"test"}'

# Expected: {"text":"Success","code":0}
```

**Expected:** JSON response with `"code":0` indicating success

## Test 4: Set Environment Variables

```bash
export MARIADB_API_KEY="your-actual-api-key"
export MARIADB_API_URL="https://api.skysql.com"
export SPLUNK_HEC_URL="https://inputs.your-instance.splunkcloud.com:8088"
export SPLUNK_HEC_TOKEN="your-actual-hec-token"
export SPLUNK_INDEX="mariadb_metrics"
export SPLUNK_SOURCE="mariadbl_metrics_api"
export SPLUNK_SOURCETYPE="metrics"
```

**Verify:**
```bash
echo $MARIADB_API_KEY
echo $SPLUNK_HEC_TOKEN
```

## Test 5: Run Python Script Directly

```bash
cd <target-dir>/splunk-integration
python3 metrics/scripts/mariadb_metrics_collector.py
```

**Expected Output:**
```
INFO: Configuration validated successfully
INFO: MariaDB Cloud API URL: https://api.skysql.com
INFO: Splunk HEC URL: https://inputs.your-instance.splunkcloud.com:8088
INFO: Starting MariaDB Cloud metrics collection
INFO: Fetching metrics from MariaDB Cloud API (attempt 1/3)
INFO: Successfully fetched metrics (XXXX bytes)
INFO: Parsed XX metrics from Prometheus format
INFO: Transformed XX metrics to HEC event format
INFO: Sending batch 1/X (XX events)
INFO: Batch 1 sent successfully
INFO: Successfully sent XX/XX events to Splunk HEC
INFO: Metrics collection completed successfully
```

**Check for errors:**
- Authentication failures
- Network connectivity issues
- Parsing errors

## Test 6: Run Wrapper Script

```bash
cd <target-dir>/splunk-integration
./metrics/scripts/mariadb_metrics_wrapper.sh
```

**Expected:** Same output as Test 5, plus wrapper script logging

## Test 7: Verify Splunk Data

```spl
# Preview recent metric data points (metrics index → use mpreview)
| mpreview index=mariadb_metrics filter="source=mariadbl_metrics_api" earliest=-5m
```

**Expected:**
```json
{
  "last_poll_time": 1234567890.123,
  "last_poll_datetime": "2026-01-25T09:00:00.123456"
}
```

## Test 8: Verify Metrics in Splunk Cloud

Log into your Splunk Cloud instance and run these searches:

> **Note:** `mariadb_metrics` is a **Metrics-type index**, so these use the
> metrics search commands (`mstats` / `mpreview` / `mcatalog`) rather than the
> event-style `index=… | stats/timechart` pipeline.

### Search 1: Check if data is arriving
```spl
| mstats count WHERE index=mariadb_metrics AND source=mariadbl_metrics_api AND metric_name="mariadb.*"
```

**Expected:** Count > 0

### Search 2: View metric names
```spl
| mstats count WHERE index=mariadb_metrics AND source=mariadbl_metrics_api AND metric_name="mariadb.*" BY metric_name
| sort - count
```

**Expected:** List of metrics starting with `mariadb.mariadb_`

### Search 3: View a specific metric over time
```spl
| mstats avg(_value) WHERE index=mariadb_metrics AND metric_name="mariadb.mariadb_server_cpu" span=1m BY server_name
```

**Expected:** Time series showing CPU usage

### Search 4: Check all dimensions
```spl
| mpreview index=mariadb_metrics filter="source=mariadbl_metrics_api"
| head 1
| transpose
```

**Expected:** Fields including `namespace`, `server_name`, `service_name`, `topology_type`

## Test 9: Test Error Handling

### Test with Invalid API Key
```bash
export MARIADB_API_KEY="invalid-key"
python3 metrics/scripts/mariadb_metrics_collector.py
```

**Expected:** Error message about authentication failure

### Test with Invalid HEC Token
```bash
export MARIADB_API_KEY="your-valid-key"
export SPLUNK_HEC_TOKEN="invalid-token"
python3 metrics/scripts/mariadb_metrics_collector.py
```

**Expected:** Error message about HEC authentication failure

## Test 10: Test Multiple Runs

```bash
# Run script twice to verify consistency
./metrics/scripts/mariadb_metrics_wrapper.sh
sleep 5
./metrics/scripts/mariadb_metrics_wrapper.sh
```

**Expected:** Both runs complete successfully with metrics sent to Splunk

## Common Issues and Solutions

### Issue: ModuleNotFoundError: No module named 'requests'
**Solution:**
```bash
pip3 install requests
```

### Issue: Authentication failed - check MARIADB_API_KEY
**Solution:**
- Verify API key is correct
- Check API key has not expired
- Ensure API key has read access to Observability API

### Issue: HEC authentication failed
**Solution:**
- Verify HEC token is correct
- Check HEC is enabled in Splunk Cloud
- Verify token has write access to the target index

### Issue: No metrics appearing in Splunk
**Solution:**
```spl
# Check internal logs
index=_internal sourcetype=splunkd component=HttpEventCollector
| search "mariadbl_metrics_api"

# Check if data is in different index
index=* source=mariadbl_metrics_api
```

### Issue: Permission denied on log files
**Solution:**
```bash
# Ensure log directory is writable
mkdir -p /var/log
chmod 755 /var/log
```

## Success Criteria

- [x] Python script runs without errors
- [x] Metrics fetched from MariaDB Cloud API
- [x] Metrics parsed from Prometheus format
- [x] Metrics transformed to HEC format
- [x] Metrics sent to Splunk HEC successfully
- [x] Metrics visible in Splunk Cloud Platform
- [x] All expected fields present (metric_name, _value, dimensions)
- [x] Time series data displays correctly in Splunk

## Next Steps After Successful Testing

1. **Schedule Regular Execution:**
   - Set up cron job (every 1-5 minutes)
   - Or configure systemd timer
   - Or deploy Kubernetes CronJob

2. **Create Splunk Dashboards:**
   - CPU usage trends
   - Connection metrics
   - Query performance
   - Storage utilization

3. **Set Up Alerts:**
   - High CPU usage
   - Connection spikes
   - Slow query increases
   - No data received (monitoring)

4. **Production Deployment:**
   - Use production API keys
   - Configure proper checkpoint location
   - Set up log rotation
   - Enable monitoring and alerting
