# MariaDB Cloud Splunk Integration Package

This package contains integrations for sending MariaDB Cloud (formerly SkySQL) logs and metrics to Splunk.

## Integrations

This package provides two separate integrations:

1. **Logs Integration** - Sends MariaDB Cloud logs to Splunk Universal Forwarder
2. **Metrics Integration** - Sends MariaDB Cloud metrics to Splunk Cloud Platform via HEC

Both integrations are completely independent and can be deployed separately or together.

---

## Logs Integration

### How It Works

The logs integration uses a two-step process to fetch logs from MariaDB Cloud:

1. **Query for Log Metadata**: Calls `/observability/v2/logs/query` to get metadata about available log files
2. **Fetch Log Archives**: Uses the log IDs from step 1 to download actual log archives via `/observability/v2/logs/archive`
3. **Extract & Parse**: Extracts individual log lines from the tar.gz archives and outputs them to Splunk

This approach ensures you get the complete, raw log content rather than just metadata.

### Package Contents

```
splunk-integration/
├── README.md                            # This file
├── scripts/
│   ├── skysql_logs_input.py            # Logs: Python script for API polling
│   ├── skysql_logs_wrapper.sh          # Logs: Wrapper script with environment variables
│   ├── mariadb_metrics_input.py        # Metrics: Python script for metrics collection
│   └── mariadb_metrics_wrapper.sh      # Metrics: Wrapper script for metrics
├── default/
│   ├── inputs.conf                      # Logs: Splunk inputs configuration
│   ├── props.conf                       # Logs: Field extraction and parsing rules
│   └── app.conf                         # App metadata
├── local/
│   └── outputs.conf.example             # Example outputs configuration
└── metrics/
    ├── README.md                        # Metrics integration documentation
    ├── config.yaml.example              # Metrics configuration template
    └── .gitignore                       # Metrics-specific gitignore

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
- MariaDB Cloud API: https://apidocs.skysql.com/
- MariaDB Cloud Documentation: https://docs.skysql.com/Observability/

---

## Metrics Integration

The metrics integration collects metrics from the MariaDB Cloud Observability API and sends them to Splunk Cloud Platform via HTTP Event Collector (HEC).

### Quick Start

1. **Prerequisites**:
   - MariaDB Cloud API key
   - Splunk Cloud Platform with HEC enabled
   - HEC token with write access to target index
   - Python 3.7+ with `requests` library

2. **Configuration**:
   ```bash
   export MARIADB_API_KEY="your-api-key"
   export SPLUNK_HEC_TOKEN="your-hec-token"
   export SPLUNK_HEC_URL="https://inputs.prd-p-29k1h.splunkcloud.com:8088"
   ```

3. **Run**:
   ```bash
   ./scripts/mariadb_metrics_wrapper.sh
   ```

4. **Verify in Splunk**:
   ```spl
   index=main sourcetype=metrics source=mariadbl_metrics_api
   | stats count by metric_name
   ```

### Full Documentation

For complete installation, configuration, deployment options, and troubleshooting, see:
- **[metrics/README.md](metrics/README.md)** - Complete metrics integration documentation
- **[metrics/metrics-list.md](metrics/metrics-list.md)** - Complete reference of all 89 available metrics
- **[metrics/examples/](metrics/examples/)** - Ready-to-use deployment examples (cron, systemd, launchd, Kubernetes)

### Key Features

- **89 Metrics**: Collects 76 MariaDB + 13 MaxScale metrics covering connection, performance, resource utilization, InnoDB operations, and replication
- **Prometheus Format**: Parses metrics in Prometheus exposition format
- **Checkpoint Mechanism**: Prevents duplicate data with state tracking
- **Batch Processing**: Configurable batch size for HEC ingestion
- **Flexible Deployment**: Supports cron, systemd, and Kubernetes CronJob

### Architecture

```
MariaDB Cloud API → Python Script → Parse Prometheus → Transform to HEC → Splunk Cloud Platform
```

The metrics integration is completely separate from the logs integration and can be deployed independently.
