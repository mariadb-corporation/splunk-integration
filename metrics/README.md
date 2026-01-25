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

- **Prometheus Format Support**: Parses metrics in Prometheus exposition format
- **Checkpoint Mechanism**: Tracks last successful poll to prevent duplicate data
- **Batch Processing**: Sends metrics in configurable batches (default: 100 events)
- **Retry Logic**: Automatic retry with exponential backoff for failed API calls
- **Error Handling**: Comprehensive error handling and logging
- **Flexible Deployment**: Supports standalone execution, cron jobs, systemd timers, and Kubernetes CronJobs

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
- Cron or systemd (for scheduled execution)
- Kubernetes cluster (for CronJob deployment)

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
| `METRICS_CHECKPOINT_FILE` | No | `/var/lib/mariadb/metrics_checkpoint.json` | Checkpoint file location |
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
  hec_url: https://inputs.prd-p-29k1h.splunkcloud.com:8088
  hec_token: ${SPLUNK_HEC_TOKEN}
  index: main
  source: mariadbl_metrics_api
  sourcetype: metrics
  verify_ssl: true

collection:
  poll_interval: 60
  checkpoint_file: /var/lib/mariadb/metrics_checkpoint.json
  batch_size: 100
```

## Deployment Options

### Option 1: Manual Execution

Run the script directly:

```bash
export MARIADB_API_KEY="your-api-key"
export SPLUNK_HEC_TOKEN="your-hec-token"
export SPLUNK_HEC_URL="https://inputs.prd-p-29k1h.splunkcloud.com:8088"

./scripts/mariadb_metrics_wrapper.sh
```

### Option 2: Cron Job

Schedule periodic execution:

```bash
# Edit crontab
crontab -e

# Add entry (runs every minute)
*/1 * * * * /opt/splunk-integration/scripts/mariadb_metrics_wrapper.sh >> /var/log/mariadb_metrics.log 2>&1
```

Or create a system cron file:

```bash
# /etc/cron.d/mariadb-metrics
*/1 * * * * root /opt/splunk-integration/scripts/mariadb_metrics_wrapper.sh >> /var/log/mariadb_metrics.log 2>&1
```

### Option 3: Systemd Timer

Create systemd service and timer:

**Service file** (`/etc/systemd/system/mariadb-metrics.service`):

```ini
[Unit]
Description=MariaDB Cloud Metrics Collection
After=network.target

[Service]
Type=oneshot
User=splunk
Environment="MARIADB_API_KEY=your-api-key"
Environment="SPLUNK_HEC_TOKEN=your-hec-token"
Environment="SPLUNK_HEC_URL=https://inputs.prd-p-29k1h.splunkcloud.com:8088"
ExecStart=/opt/splunk-integration/scripts/mariadb_metrics_wrapper.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Timer file** (`/etc/systemd/system/mariadb-metrics.timer`):

```ini
[Unit]
Description=MariaDB Cloud Metrics Collection Timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=1s

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mariadb-metrics.timer
sudo systemctl start mariadb-metrics.timer
sudo systemctl status mariadb-metrics.timer
```

### Option 4: Kubernetes CronJob

Deploy as a Kubernetes CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mariadb-metrics-collector
  namespace: monitoring
spec:
  schedule: "*/1 * * * *"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: metrics-collector
            image: python:3.9-slim
            command: ["/scripts/mariadb_metrics_wrapper.sh"]
            env:
            - name: MARIADB_API_KEY
              valueFrom:
                secretKeyRef:
                  name: mariadb-credentials
                  key: api-key
            - name: SPLUNK_HEC_TOKEN
              valueFrom:
                secretKeyRef:
                  name: splunk-credentials
                  key: hec-token
            - name: SPLUNK_HEC_URL
              value: "https://inputs.prd-p-29k1h.splunkcloud.com:8088"
            - name: SPLUNK_INDEX
              value: "main"
            volumeMounts:
            - name: scripts
              mountPath: /scripts
            - name: checkpoint
              mountPath: /var/lib/mariadb
          volumes:
          - name: scripts
            configMap:
              name: mariadb-metrics-scripts
              defaultMode: 0755
          - name: checkpoint
            persistentVolumeClaim:
              claimName: mariadb-metrics-checkpoint
```

## Verification and Testing

### Test Connection to MariaDB Cloud API

```bash
curl -H "X-Api-Key: your-api-key" \
     https://api.skysql.com/observability/v2/metrics
```

### Test Connection to Splunk HEC

```bash
curl -k https://inputs.prd-p-29k1h.splunkcloud.com:8088/services/collector \
     -H "Authorization: Splunk your-hec-token" \
     -d '{"event":"test","sourcetype":"manual"}'
```

### Run Script Manually

```bash
export MARIADB_API_KEY="your-api-key"
export SPLUNK_HEC_TOKEN="your-hec-token"
export SPLUNK_HEC_URL="https://inputs.prd-p-29k1h.splunkcloud.com:8088"

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

### Issue: Checkpoint File Permission Denied

**Error**: `Failed to save checkpoint: Permission denied`

**Solution**:
```bash
# Create checkpoint directory with proper permissions
sudo mkdir -p /var/lib/mariadb
sudo chown splunk:splunk /var/lib/mariadb
sudo chmod 755 /var/lib/mariadb
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

### Monitor Checkpoint

```bash
# View last successful poll
cat /var/lib/mariadb/metrics_checkpoint.json
```

### Create Splunk Alerts

```spl
# Alert if no metrics received in 5 minutes
index=main sourcetype=metrics source=mariadbl_metrics_api
| stats latest(_time) as last_event
| eval age=now()-last_event
| where age > 300
```

## Security Best Practices

1. **Never hardcode credentials** - Use environment variables or secrets management
2. **Restrict file permissions** - Checkpoint file should be 600, owned by service user
3. **Use HTTPS only** - All API calls use SSL/TLS
4. **Rotate credentials regularly** - Update API keys and HEC tokens periodically
5. **Limit API key scope** - Use read-only API keys with minimal permissions

## Support

For issues or questions:
- GitHub Issues: https://github.com/mariadb-corporation/splunk-integration/issues
- MariaDB Support: https://mariadb.com/support/
- Splunk Documentation: https://docs.splunk.com/

## License

See LICENSE file in the repository root.
