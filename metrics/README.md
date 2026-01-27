# MariaDB Cloud Metrics Integration for Splunk Cloud Platform

This integration collects metrics from the MariaDB Cloud Observability API and sends them to Splunk Cloud Platform via HTTP Event Collector (HEC).

## Overview

The MariaDB Cloud Metrics integration polls the MariaDB Cloud Observability API at regular intervals, retrieves metrics in Prometheus format, transforms them to Splunk HEC event format, and sends them to your Splunk Cloud Platform instance.

**Available Metrics:** This integration collects **89 metrics** (76 MariaDB + 13 MaxScale) covering database performance, resource utilization, connections, queries, InnoDB operations, and replication status. See [metrics-list.md](metrics-list.md) for the complete metrics reference.

### Architecture

```
MariaDB Cloud API → Python Script → Parse Prometheus → Transform to HEC → Splunk Cloud Platform
                    (mariadb_metrics_input.py)                              (HEC Endpoint)
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
   - HTTP Event Collector (HEC) enabled
   - HEC token created with write access to target index

3. **Python 3.7+**
   - `requests` library (install via `pip install requests`)

### Optional

- Splunk Universal Forwarder (for integrated deployment)
- systemd (Linux) or launchd (macOS) for service management
- Kubernetes cluster (for containerized deployment)

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

Copy the example configuration:

```bash
cp metrics/config.yaml.example metrics/config.yaml
```

Edit `metrics/config.yaml` or set environment variables:

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
| `SPLUNK_INDEX` | No | `main` | Target Splunk index |
| `SPLUNK_SOURCE` | No | `mariadbl_metrics_api` | Source identifier |
| `SPLUNK_SOURCETYPE` | No | `metrics` | Source type |
| `METRICS_BATCH_SIZE` | No | `100` | Number of events per HEC batch |
| `METRICS_MAX_RETRIES` | No | `3` | Maximum retry attempts |
| `METRICS_RETRY_DELAY` | No | `5` | Retry delay in seconds |

### Configuration File

Alternatively, use `metrics/config.yaml`:

```yaml
mariadb:
  api_url: https://api.skysql.com
  api_key: ${MARIADB_API_KEY}
  metrics_endpoint: /observability/v2/metrics

splunk_cloud:
  hec_url: https://inputs.your-instance.splunkcloud.com:8088
  hec_token: ${SPLUNK_HEC_TOKEN}
  index: main
  source: mariadbl_metrics_api
  sourcetype: metrics
  verify_ssl: true

collection:
  poll_interval: 60
  batch_size: 100
```

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
```bash
python3 metrics/scripts/mariadb_metrics_input.py --daemon --interval 60

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
  --from-file=mariadb_metrics_input.py=metrics/scripts/mariadb_metrics_input.py \
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
python3 metrics/scripts/mariadb_metrics_input.py

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

./scripts/mariadb_metrics_wrapper.sh
```

### Verify Metrics in Splunk

Search for metrics in Splunk Cloud Platform:

```spl
index=main sourcetype=metrics source=mariadbl_metrics_api
| stats count by metric_name

index=main sourcetype=metrics metric_name="mariadb.mariadb_server_cpu"
| timechart avg(_value) by server_name

index=main sourcetype=metrics metric_name="mariadb.mariadb_global_status_threads_connected"
| timechart avg(_value) by service_name
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
# Check all data from source
index=* source=mariadbl_metrics_api

# Check HEC internal logs
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
index=main sourcetype=metrics source=mariadbl_metrics_api
| stats latest(_time) as last_event
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
