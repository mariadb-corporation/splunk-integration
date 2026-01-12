# Quick Start Guide - SkySQL Logs in Splunk

### Prerequisites
- Splunk Universal Forwarder installed
- SkySQL API Key
- Python 3.x with `requests` library

## 1-minute Setup

Extract the zip file and execute install.sh script. This assumes that you have splunk universal forwarder installed in the default location `/opt/splunkforwarder` on a Linux machine.

```bash
./install.sh
```

## 5-Minute Setup

Here are the steps to setup the integration in details:

### Installation Steps

```bash
# 1. Copy configuration app to Splunk
sudo mkdir -p /opt/splunkforwarder/etc/apps/splunk-skysql-integration
sudo cp -r splunk-skysql-integration/default \
  /opt/splunkforwarder/etc/apps/splunk-skysql-integration/
sudo cp -r splunk-skysql-integration/local \
  /opt/splunkforwarder/etc/apps/splunk-skysql-integration/

# 2. Copy scripts to Splunk bin/scripts
sudo mkdir -p /opt/splunkforwarder/bin/scripts
sudo cp splunk-skysql-integration/scripts/*.sh /opt/splunkforwarder/bin/scripts/
sudo cp splunk-skysql-integration/scripts/*.py /opt/splunkforwarder/bin/scripts/

# 3. Install Python dependencies
/opt/splunkforwarder/bin/splunk cmd python3 -m pip install requests

# 4. Configure API key
sudo vi /opt/splunkforwarder/bin/scripts/skysql_logs_wrapper.sh
# Replace: your-api-key-here

# 5. Set permissions
sudo chmod +x /opt/splunkforwarder/bin/scripts/skysql_logs_wrapper.sh
sudo chmod +x /opt/splunkforwarder/bin/scripts/skysql_logs_input.py
sudo chown -R splunk:splunk /opt/splunkforwarder/etc/apps/splunk-skysql-integration
sudo chown -R splunk:splunk /opt/splunkforwarder/bin/scripts

# 6. Restart Splunk
sudo /opt/splunkforwarder/bin/splunk restart
```

### Verification

```bash
# Test the script manually
cd /opt/splunkforwarder/bin/scripts
sudo -u splunk ./skysql_logs_wrapper.sh

# Check logs
tail -f /opt/splunkforwarder/var/log/splunk/splunkd.log | grep skysql
```

### Search in Splunk

```spl
index=skysql earliest=-1h
```

## Common Splunk Searches

### View All SkySQL Logs
```spl
index=skysql sourcetype=skysql:logs
| table _time, event.logType, event.server, event.message
```

### Error Logs Only
```spl
index=skysql sourcetype=skysql:logs event.logType="error-log"
| table _time, event.server, event.message
| sort -_time
```

### Logs by Server
```spl
index=skysql sourcetype=skysql:logs
| stats count by event.server, event.logType
| sort -count
```

### MaxScale Logs
```spl
index=skysql sourcetype=skysql:logs event.logType="maxscale-log"
| table _time, event.server, event.message
```

### Logs in Last Hour
```spl
index=skysql sourcetype=skysql:logs earliest=-1h
| timechart count by event.logType
```

### Search for Specific Error
```spl
index=skysql sourcetype=skysql:logs event.message="*error*"
| table _time, event.server, event.logType, event.message
```

### Log Volume by Service
```spl
index=skysql sourcetype=skysql:logs
| timechart span=5m count by event.service
```

### Top 10 Servers by Log Count
```spl
index=skysql sourcetype=skysql:logs
| stats count by event.server
| sort -count
| head 10
```

## Dashboard Examples

### Create a SkySQL Logs Dashboard

1. In Splunk, go to **Dashboards** > **Create New Dashboard**
2. Name it "SkySQL Logs Overview"
3. Add the following panels:

#### Panel 1: Log Volume Over Time
```spl
index=skysql sourcetype=skysql:logs
| timechart span=5m count by event.logType
```

#### Panel 2: Logs by Server
```spl
index=skysql_logs sourcetype=skysql:logs
| stats count by event.server
| sort -count
```

#### Panel 3: Recent Error Logs
```spl
index=skysql sourcetype=skysql:logs event.logType="error-log"
| table _time, event.server, event.message
| sort -_time
| head 20
```

#### Panel 4: Log Type Distribution
```spl
index=skysql sourcetype=skysql:logs
| stats count by event.logType
```

## Alerts

### Alert on High Error Rate

```spl
index=skysql sourcetype=skysql:logs event.logType="error-log"
| stats count as error_count
| where error_count > 100
```

**Trigger Condition:** Number of Results > 0  
**Time Range:** Last 15 minutes  
**Cron Schedule:** */15 * * * * (every 15 minutes)

### Alert on Specific Server Issues

```spl
index=skysql sourcetype=skysql:logs event.server="your-server-id" event.message="*critical*"
| table _time, event.logType, event.message
```

**Trigger Condition:** Number of Results > 0  
**Time Range:** Last 5 minutes  
**Cron Schedule:** */5 * * * * (every 5 minutes)

## Troubleshooting

### No logs appearing?

1. **Check API key:**
   ```bash
   curl -H "X-API-KEY: your-key" https://api.skysql.com/observability/v2/logs/types
   ```

2. **Test script manually:**
   ```bash
   cd /opt/splunkforwarder/etc/apps/splunk-skysql-integration/scripts
   sudo -u splunk ./skysql_logs_wrapper.sh
   ```

3. **Check Splunk logs:**
   ```bash
   tail -f /opt/splunkforwarder/var/log/splunk/splunkd.log | grep -i error
   ```

### Script errors?

Check Python dependencies:
```bash
/opt/splunkforwarder/bin/splunk cmd python3 -c "import requests; print('OK')"
```

### Permission issues?

Fix ownership:
```bash
sudo chown -R splunk:splunk /opt/splunkforwarder/etc/apps/splunk-skysql-integration
sudo chmod +x /opt/splunkforwarder/bin/scripts/*.sh
sudo chmod +x /opt/splunkforwarder/bin/scripts/*.py
```

## Advanced Configuration

### Change Polling Interval

Edit `/opt/splunkforwarder/etc/apps/splunk-skysql-integration/default/inputs.conf`:

```ini
interval = 600  # Poll every 10 minutes instead of 5
```

### Filter Specific Log Types

Edit the Python script to add filters:

```python
payload = {
    'fromDate': from_date,
    'toDate': to_date,
    'limit': limit,
    'offset': offset,
    'logType': ['error-log'],  # Only error logs
    'orderByField': 'timestamp',
    'orderByDirection': 'asc'
}
```

### Multiple Environments

Create separate app instances for different environments:

```bash
cp -r splunk-skysql-integration splunk-skysql-production
cp -r splunk-skysql-integration splunk-skysql-staging

# Configure each with different API keys and index names
```

## Support

- **SkySQL API Docs:** https://apidocs.skysql.com/
- **SkySQL Observability:** https://docs.skysql.com/Observability/
- **Splunk Docs:** https://docs.splunk.com/
