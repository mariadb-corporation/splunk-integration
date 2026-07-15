# MariaDB Cloud Metrics Integration for Splunk Cloud Platform

This integration collects metrics from the MariaDB Cloud Observability API and sends them to Splunk Cloud Platform via HTTP Event Collector (HEC).

## Overview

The MariaDB Cloud Metrics integration polls the MariaDB Cloud Observability API at regular intervals, retrieves metrics in Prometheus format, transforms them to Splunk HEC event format, and sends them to your Splunk Cloud Platform instance.

**Available Metrics:** This integration collects **89 metrics** (76 MariaDB + 13 MaxScale) covering database performance, resource utilization, connections, queries, InnoDB operations, and replication status. See [metrics-list.md](metrics-list.md) for the complete metrics reference.

### Architecture

```
MariaDB Cloud API → Python Script → Parse Prometheus → Transform to HEC → Splunk Cloud Platform
                    (mariadb_metrics_collector.py)                              (HEC Endpoint)
```

### Key Features

- **Daemon Mode**: Runs as a persistent process with continuous polling (recommended)
- **Prometheus Format Support**: Parses metrics in Prometheus exposition format
- **Batch Processing**: Sends metrics in configurable batches (default: 100 events)
- **Retry Logic**: Automatic retry with exponential backoff for failed API calls
- **Graceful Shutdown**: Handles SIGTERM/SIGINT for clean shutdowns
- **Error Handling**: Comprehensive error handling and logging
- **Flexible Deployment**: Supports daemon mode, standalone execution, cron jobs (legacy), systemd services, and Kubernetes Deployments

## Prerequisites

### Required

1. **MariaDB Cloud API Key**
   - Obtain from MariaDB Cloud console
   - Requires read access to Observability API

2. **Splunk Cloud Platform**
   - Active Splunk Cloud instance
   - A target index created as a **Metrics-type index** (index data type
     `Metrics`, **not** Events/log type). The collector sends HEC
     metric-format events (`"event": "metric"` with `metric_name` / `_value`
     in `fields`), which are only ingested correctly by a metrics index.
   - HTTP Event Collector (HEC) enabled
   - HEC token created with write access to that metrics index

3. **Python 3.7+**
   - `requests` library (install via `pip install requests`)

### Optional

- systemd (Linux) or launchd (macOS) for service management
- Kubernetes cluster (for containerized deployment)

The collector sends metrics **directly to Splunk Cloud via HEC** — a Splunk
Universal Forwarder is not required.

## Installation

### Step 1: Clone Repository

```bash
cd /opt
git clone https://github.com/mariadb-corporation/splunk-integration.git
cd splunk-integration
```

### Step 2: Install Python Dependencies

```bash
pip3 install requests
```

### Step 3: Configure Environment Variables

Set the required environment variables:

```bash
export MARIADB_API_KEY="your-mariadb-api-key"
export SPLUNK_HEC_TOKEN="your-splunk-hec-token"
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MARIADB_API_KEY` | Yes | - | MariaDB Cloud API key |
| `MARIADB_API_URL` | No | `https://api.skysql.com` | MariaDB Cloud API base URL |
| `SPLUNK_HEC_URL` | Yes | - | Splunk HEC endpoint URL (without path) |
| `SPLUNK_HEC_TOKEN` | Yes | - | Splunk HEC authentication token |
| `SPLUNK_HEC_VERIFY_SSL` | No | `true` | Verify SSL certificates for HEC connection (`true`/`false`) |
| `SPLUNK_INDEX` | No | `mariadb_metrics` | Target Splunk index (must be a **Metrics-type** index) |
| `SPLUNK_SOURCE` | No | `mariadbl_metrics_api` | Source identifier |
| `SPLUNK_SOURCETYPE` | No | `metrics` | Source type |
| `METRICS_BATCH_SIZE` | No | `100` | Number of events per HEC batch |
| `METRICS_MAX_RETRIES` | No | `3` | Maximum retry attempts |
| `METRICS_RETRY_DELAY` | No | `5` | Retry delay in seconds |

> **Note:** The collector reads configuration **only** from the environment
> variables above. There is no config file — the Python script does not read
> YAML or any other config file.

## Deployment Options

**📁 Ready-to-use deployment examples are available in the [`examples/`](examples/) directory** with sanitized configuration files for all deployment methods below.

### 🚀 Recommended: Daemon Mode

**Daemon mode is the recommended approach** for deployments. The collector runs as a persistent process and polls metrics at regular intervals.

**Benefits:**
- ✅ Single persistent process (no repeated startup overhead)
- ✅ Configurable polling interval
- ✅ Graceful shutdown handling
- ✅ Automatic restart on failure (with systemd/launchd)
- ✅ Better resource utilization

**CLI Options:**
- `--daemon`: Run continuously (polling loop)
- `--interval N`: Polling interval in seconds (default: 60)
- `--verbose`: Enable DEBUG logging (e.g. Prometheus line-parse failures)

```bash
python3 metrics/scripts/mariadb_metrics_collector.py --daemon --interval 60
```

### Option 1: Daemon Mode with systemd (Linux) ⭐

Run as a persistent systemd service:

```bash
# See examples/systemd-example.service for full configuration
sudo systemctl enable mariadb-metrics.service
sudo systemctl start mariadb-metrics.service
sudo systemctl status mariadb-metrics.service
```

**Configuration:** Service runs in daemon mode with 60 second interval and automatic restart on failure.

### Option 2: Daemon Mode with launchd (macOS) ⭐

Run as a persistent macOS service:

```bash
# See examples/launchd-example.plist for full configuration
cp examples/launchd-example.plist ~/Library/LaunchAgents/com.mariadb.metrics.plist
launchctl load ~/Library/LaunchAgents/com.mariadb.metrics.plist
launchctl list | grep mariadb
```

**Configuration:** Service runs in daemon mode with 60 second interval and automatic restart on failure.

### Option 3: Kubernetes Deployment ⭐

Deploy as a Kubernetes Deployment for containerized environments:

```bash
# See examples/kubernetes-deployment-example.yaml for full configuration

# Create ConfigMap from Python script
kubectl create configmap mariadb-metrics-script \
  --from-file=mariadb_metrics_collector.py=metrics/scripts/mariadb_metrics_collector.py \
  -n mariadb-monitoring

# Apply deployment
kubectl apply -f examples/kubernetes-deployment-example.yaml

# Verify
kubectl get deployment -n mariadb-monitoring
kubectl logs -f deployment/mariadb-metrics-collector -n mariadb-monitoring
```

**Configuration:** Deployment runs in daemon mode with configurable interval via ConfigMap.

### Option 4: Standalone Execution (Testing)

Run manually for testing:

```bash
# Run once
python3 metrics/scripts/mariadb_metrics_collector.py

# Or via wrapper (sets environment variables)
./metrics/scripts/mariadb_metrics_wrapper.sh
```

### Option 5: Cron Job (Legacy)

**Note:** Daemon mode is recommended over cron.

```bash
# See examples/cron-example.sh for full configuration
crontab -e
# Add: */1 * * * * /opt/splunk-integration/metrics/scripts/mariadb_metrics_wrapper.sh >> /var/log/mariadb_metrics.log 2>&1
```

## Verification and Testing

### Test Connection to MariaDB Cloud API

```bash
curl -H "X-Api-Key: your-api-key" \
     https://api.skysql.com/observability/v2/metrics
```

### Test Connection to Splunk HEC

```bash
curl -k https://inputs.your-instance.splunkcloud.com:8088/services/collector \
     -H "Authorization: Splunk your-hec-token" \
     -d '{"event":"test","sourcetype":"manual"}'
```

### Run Script Manually

```bash
export MARIADB_API_KEY="your-api-key"
export SPLUNK_HEC_TOKEN="your-hec-token"
export SPLUNK_HEC_URL="https://inputs.your-instance.splunkcloud.com:8088"

./metrics/scripts/mariadb_metrics_wrapper.sh
```

### Verify Metrics in Splunk

Search for metrics in Splunk Cloud Platform. Because the target is a
**Metrics-type index**, use the metrics search commands (`mstats` / `mpreview`),
not the event-style `index=… | stats/timechart` pipeline:

```spl
| mstats count WHERE index=mariadb_metrics AND source=mariadbl_metrics_api AND metric_name="mariadb.*" BY metric_name

| mstats avg(_value) WHERE index=mariadb_metrics AND metric_name="mariadb.mariadb_server_cpu" span=1m BY server_name

| mstats avg(_value) WHERE index=mariadb_metrics AND metric_name="mariadb.mariadb_global_status_threads_connected" span=1m BY service_name
```

## Troubleshooting

### Issue: Authentication Failed

**Error**: `Authentication failed - check MARIADB_API_KEY`

**Solution**:
- Verify API key is correct
- Check API key has not expired
- Ensure API key has read access to Observability API

### Issue: HEC Connection Failed

**Error**: `HEC authentication failed - check SPLUNK_HEC_TOKEN`

**Solution**:
- Verify HEC token is correct
- Check HEC is enabled in Splunk Cloud
- Verify HEC endpoint URL is correct
- Check firewall/network connectivity

### Issue: No Metrics Appearing in Splunk

**Possible Causes**:
1. Wrong index specified
2. HEC token doesn't have write access to index
3. Metrics are being sent but search query is incorrect

**Solution**:
```spl
# Preview raw metric data points from this source (metrics index)
| mpreview index=mariadb_metrics filter="source=mariadbl_metrics_api"

# Check HEC internal logs (events index)
index=_internal sourcetype=splunkd component=HttpEventCollector
```

### Issue: Python Module Not Found

**Error**: `ModuleNotFoundError: No module named 'requests'`

**Solution**:
```bash
pip3 install requests
```

## Available Metrics

The integration collects 89 metrics from MariaDB Cloud:

### Connection Metrics
- `mariadb.mariadb_global_status_threads_connected` - Active connections
- `mariadb.mariadb_global_status_threads_running` - Running threads
- `mariadb.mariadb_global_status_aborted_clients` - Aborted connections

### Performance Metrics
- `mariadb.mariadb_global_status_queries` - Total queries
- `mariadb.mariadb_global_status_slow_queries` - Slow queries
- `mariadb.mariadb_global_status_questions` - Client statements

### Resource Metrics
- `mariadb.mariadb_server_cpu` - CPU usage percentage
- `mariadb.mariadb_server_memory_rss` - Resident memory
- `mariadb.mariadb_server_volume_stats_used_bytes` - Storage used

### InnoDB Metrics
- `mariadb.mariadb_global_status_innodb_data_read` - InnoDB data read
- `mariadb.mariadb_global_status_innodb_data_written` - InnoDB data written
- `mariadb.mariadb_global_status_buffer_pool_pages` - Buffer pool pages

For a complete list of metrics, see `metrics-list.md`.

## Monitoring

### Check Script Execution

```bash
# View logs
tail -f /var/log/mariadb_metrics.log

# Check systemd status
sudo systemctl status mariadb-metrics.service

# View systemd logs
sudo journalctl -u mariadb-metrics.service -f
```

### Create Splunk Alerts

```spl
# Alert if no metrics received in 5 minutes
| mstats count WHERE index=mariadb_metrics AND metric_name="mariadb.*" span=1m
| stats max(_time) as last_event
| eval age=now()-last_event
| where age > 300
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/mariadb-corporation/splunk-integration/issues
- MariaDB Support: https://mariadb.com/support/
- Splunk Documentation: https://docs.splunk.com/

## License

See LICENSE file in the repository root.
