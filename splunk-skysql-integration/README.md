# SkySQL Splunk Universal Forwarder Integration Package

This package contains all necessary files to integrate SkySQL Logs API with Splunk Universal Forwarder.

## How It Works

The integration uses a two-step process to fetch logs from SkySQL:

1. **Query for Log Metadata**: Calls `/observability/v2/logs/query` to get metadata about available log files
2. **Fetch Log Archives**: Uses the log IDs from step 1 to download actual log archives via `/observability/v2/logs/archive`
3. **Extract & Parse**: Extracts individual log lines from the tar.gz archives and outputs them to Splunk

This approach ensures you get the complete, raw log content rather than just metadata.

## Package Contents

```
splunk-skysql-integration/
├── README.md                            # This file
├── scripts/
│   ├── skysql_logs_input.py            # Main Python script for API polling
│   └── skysql_logs_wrapper.sh          # Wrapper script with environment variables
├── default/
│   ├── inputs.conf                      # Splunk inputs configuration
│   ├── props.conf                       # Field extraction and parsing rules
│   └── app.conf                         # App metadata
└── local/
    └── outputs.conf.example             # Example outputs configuration

```

At runtime on the Splunk Universal Forwarder host:

- The **configuration files** from `default/` and `local/` live under
  `/opt/splunkforwarder/etc/apps/splunk-skysql-integration/`.
- The **shell and Python scripts** (`*.sh`, `*.py`) are copied to
  `/opt/splunkforwarder/bin/scripts/`.

## Installation

### 1. Copy Package to Splunk

```bash
# Create the app configuration directory
sudo mkdir -p /opt/splunkforwarder/etc/apps/splunk-skysql-integration

# Copy configuration files (default and optional local) into the app directory
sudo cp -r splunk-skysql-integration/default \
  /opt/splunkforwarder/etc/apps/splunk-skysql-integration/

# Optionally copy local/ if you want to start from the example outputs.conf
sudo cp -r splunk-skysql-integration/local \
  /opt/splunkforwarder/etc/apps/splunk-skysql-integration/

# Ensure a scripts directory exists under Splunk bin and copy the runtime scripts there
sudo mkdir -p /opt/splunkforwarder/bin/scripts
sudo cp splunk-skysql-integration/scripts/*.sh /opt/splunkforwarder/bin/scripts/
sudo cp splunk-skysql-integration/scripts/*.py /opt/splunkforwarder/bin/scripts/

# Set proper ownership
sudo chown -R splunk:splunk /opt/splunkforwarder/etc/apps/splunk-skysql-integration
sudo chown -R splunk:splunk /opt/splunkforwarder/bin/scripts
```

### 2. Configure API Key

Edit the wrapper script with your SkySQL API key:

```bash
vi /opt/splunkforwarder/bin/scripts/skysql_logs_wrapper.sh
```

Replace `your-api-key-here` with your actual SkySQL API key.

### 3. Set Script Permissions

```bash
chmod +x /opt/splunkforwarder/bin/scripts/skysql_logs_wrapper.sh
chmod +x /opt/splunkforwarder/bin/scripts/skysql_logs_input.py
```

### 4. Install Python Dependencies

```bash
/opt/splunkforwarder/bin/splunk cmd python3 -m pip install requests
```

### 5. Configure Outputs (Optional)

If you need to forward to specific indexers:

```bash
cp /opt/splunkforwarder/etc/apps/splunk-skysql-integration/local/outputs.conf.example \
   /opt/splunkforwarder/etc/apps/splunk-skysql-integration/local/outputs.conf

# Edit with your indexer details
vi /opt/splunkforwarder/etc/apps/splunk-skysql-integration/local/outputs.conf
```

### 6. Restart Splunk Universal Forwarder

```bash
/opt/splunkforwarder/bin/splunk restart
```

## Verification

### Test the Script Manually

```bash
cd /opt/splunkforwarder/bin/scripts
./skysql_logs_wrapper.sh
```

### Check Splunk Logs

```bash
tail -f /opt/splunkforwarder/var/log/splunk/splunkd.log | grep skysql
```

### Search in Splunk

```spl
# Search for archive logs (actual log content)
index=skysql sourcetype=skysql:logs earliest=-1h

# View log messages
index=skysql sourcetype=skysql:logs 
| table _time, event.filename, event.message, event.server
```

## Configuration Options

### Adjust Polling Interval

Edit `default/inputs.conf` and change the `interval` value (in seconds):

```ini
interval = 300  # Poll every 5 minutes
```

### Filter by Log Type

Edit `scripts/skysql_logs_input.py` and modify the payload:

```python
payload = {
    'fromDate': from_date,
    'toDate': to_date,
    'limit': limit,
    'offset': offset,
    'logType': ['error-log', 'maxscale-log', 'audit-log'],  # Add specific log types
    'orderByField': 'startTime',
    'orderByDirection': 'asc'
}
```

### Filter by Server

```python
payload = {
    'fromDate': from_date,
    'toDate': to_date,
    'limit': limit,
    'offset': offset,
    'serverContext': ['server-id-1', 'server-id-2'],  # Add specific servers
    'orderByField': 'startTime',
    'orderByDirection': 'asc'
}
```

## Troubleshooting

See the main documentation at `../splunk-universal-forwarder-integration.md` for detailed troubleshooting steps.

## Support

For issues or questions:
- SkySQL API: https://apidocs.skysql.com/
- SkySQL Documentation: https://docs.skysql.com/Observability/
