# MariaDB Cloud Splunk Integration Package

This package contains integrations for sending MariaDB Cloud (formerly SkySQL) logs and metrics to Splunk.

## Integrations

This package provides two separate integrations:

1. **Logs Integration** - Sends MariaDB Cloud logs to Splunk Universal Forwarder
2. **Metrics Integration** - Sends MariaDB Cloud metrics to Splunk Cloud Platform via HEC

Both integrations are completely independent and can be deployed separately or together.

---

## Logs Integration

The logs integration fetches logs from the MariaDB Cloud Observability API and sends them to Splunk Universal Forwarder.

### Package Contents

```
logs/
├── ARCHITECTURE.md                      # Architecture documentation
├── QUICKSTART.md                        # Quick start guide
├── scripts/
│   ├── skysql_logs_input.py            # Python script for API polling
│   └── skysql_logs_wrapper.sh          # Wrapper script with environment variables
├── default/                             # Default Splunk app configuration
│   ├── app.conf
│   ├── inputs.conf
│   └── props.conf
└── install.sh                           # Installation script
```

### How It Works

1. **Query for Log Metadata**: Calls `/observability/v2/logs/query` to get metadata about available log files
2. **Fetch Log Archives**: Uses the log IDs from step 1 to download actual log archives via `/observability/v2/logs/archive`
3. **Extract & Parse**: Extracts individual log lines from the tar.gz archives and outputs them to Splunk

### Quick Start

1. **Prerequisites**:
   - Splunk Universal Forwarder installed
   - MariaDB Cloud API key
   - Python 3.x with `requests` library

2. **Installation**:
   ```bash
   ./logs/install.sh
   ```

3. **Configuration**:
   ```bash
   vi /opt/splunkforwarder/bin/scripts/skysql_logs_wrapper.sh
   # Set your SKYSQL_API_KEY
   ```

4. **Verify in Splunk**:
   ```spl
   index=skysql sourcetype=skysql:logs earliest=-1h
   | table _time, event.filename, event.message, event.server
   ```

### Full Documentation

For complete installation, configuration, and troubleshooting, see:
- **[logs/ARCHITECTURE.md](logs/ARCHITECTURE.md)** - Architecture and data flow
- **[logs/QUICKSTART.md](logs/QUICKSTART.md)** - Detailed setup guide

### Key Features

- **Complete Log Content**: Fetches full log archives, not just metadata
- **Multiple Log Types**: Supports error logs, audit logs, MaxScale logs, and more
- **Server Filtering**: Filter logs by specific servers
- **Splunk Integration**: Native integration with Splunk Universal Forwarder
- **Configurable Polling**: Adjustable polling intervals

---

## Metrics Integration

The metrics integration collects metrics from the MariaDB Cloud Observability API and sends them to Splunk Cloud Platform via HTTP Event Collector (HEC).

### Package Contents

```
metrics/
├── README.md                            # Complete documentation
├── scripts/
│   ├── mariadb_metrics_input.py        # Python script for metrics collection
│   └── mariadb_metrics_wrapper.sh      # Wrapper script with environment variables
├── examples/                            # Deployment examples
│   ├── README.md
│   ├── daemon-example.sh               # Daemon mode example (recommended)
│   ├── systemd-example.service         # Linux systemd service
│   ├── launchd-example.plist           # macOS launchd service
│   ├── kubernetes-deployment-example.yaml  # Kubernetes Deployment
│   ├── kubernetes-cronjob-example.yaml # Kubernetes CronJob (legacy)
│   └── cron-example.sh                 # Cron job (legacy)
├── config.yaml.example                  # Configuration template
├── TEST_CHECKLIST.md                    # Testing guide
├── SPLUNK_DASHBOARDS.md                 # Dashboard examples
├── metrics-list.md                      # Complete metrics reference (89 metrics)
└── metricsAPI.rest                      # API reference
```

### How It Works

1. **Poll Metrics API**: Fetches metrics in Prometheus format from `/observability/v2/metrics`
2. **Parse Prometheus**: Parses Prometheus exposition format
3. **Transform to HEC**: Converts metrics to Splunk HEC event format
4. **Send to Splunk**: Sends events in batches to Splunk Cloud Platform

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

3. **Run in daemon mode** (recommended):
   ```bash
   python3 metrics/scripts/mariadb_metrics_input.py --daemon --interval 60
   ```
   
   Or run once for testing:
   ```bash
   python3 metrics/scripts/mariadb_metrics_input.py
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

- **Daemon Mode**: Runs as a persistent process with continuous polling (recommended)
- **89 Metrics**: Collects 76 MariaDB + 13 MaxScale metrics covering connection, performance, resource utilization, InnoDB operations, and replication
- **Prometheus Format**: Parses metrics in Prometheus exposition format
- **Batch Processing**: Configurable batch size for HEC ingestion
- **Graceful Shutdown**: Handles SIGTERM/SIGINT for clean shutdowns
- **Flexible Deployment**: Supports daemon mode with systemd/launchd, Kubernetes Deployments, and standalone execution

### Architecture

```
MariaDB Cloud API → Python Script → Parse Prometheus → Transform to HEC → Splunk Cloud Platform
```

The metrics integration is completely separate from the logs integration and can be deployed independently.
