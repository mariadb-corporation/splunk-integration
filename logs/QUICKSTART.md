# Quick Start Guide - MariaDB Cloud Logs in Splunk

### Prerequisites
- Splunk Cloud Platform with HTTP Event Collector (HEC) enabled
- A Splunk index for the logs (default `mariadb_logs`)
- A HEC token with write access to that index
- MariaDB Cloud API Key
- Python 3.7+ with the `requests` library (`pip3 install requests`)

## 1-Minute Setup

```bash
# 1. Install the Python dependency
pip3 install requests

# 2. Set credentials
export MARIADB_API_KEY="your-mariadb-api-key"
export SPLUNK_HEC_TOKEN="your-splunk-hec-token"
export SPLUNK_HEC_URL="https://inputs.your-instance.splunkcloud.com:8088"

# 3. Run once to verify end-to-end delivery
python3 logs/scripts/mariadb_logs_collector.py
```

Once verified, run it continuously in daemon mode:

```bash
python3 logs/scripts/mariadb_logs_collector.py --daemon --interval 300
```

For a persistent service (systemd/launchd/Kubernetes), see [`examples/`](examples/).

## Configuration

The collector is configured entirely through environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MARIADB_API_KEY` | Yes | - | MariaDB Cloud API key |
| `MARIADB_API_URL` | No | `https://api.skysql.com` | MariaDB Cloud API base URL |
| `SPLUNK_HEC_URL` | Yes | - | Splunk HEC endpoint URL (without path) |
| `SPLUNK_HEC_TOKEN` | Yes | - | Splunk HEC authentication token |
| `SPLUNK_HEC_VERIFY_SSL` | No | `true` | Verify HEC TLS certificate (`true`/`false`) |
| `SPLUNK_INDEX` | No | `mariadb_logs` | Target Splunk index |
| `SPLUNK_SOURCE` | No | `mariadb_logs_api` | Source identifier |
| `SPLUNK_SOURCETYPE` | No | `mariadb:logs` | Source type |
| `CHECKPOINT_FILE` | No | `./mariadb_checkpoint.json` | Dedup checkpoint path (use a durable location) |
| `LOGS_BATCH_SIZE` | No | `100` | Events per HEC batch |
| `LOGS_MAX_RETRIES` | No | `3` | Max retry attempts |
| `LOGS_RETRY_DELAY` | No | `5` | Retry delay in seconds |

The wrapper script `scripts/mariadb_logs_wrapper.sh` sets these variables and
runs the collector; edit it or export the variables yourself.

### Verification

```bash
# Run once via the wrapper (validates config, then does one collection cycle)
./logs/scripts/mariadb_logs_wrapper.sh

# Test the MariaDB Cloud API key directly
curl -H "X-API-KEY: your-key" https://api.skysql.com/observability/v2/logs/servers

# Test the Splunk HEC endpoint directly
curl -k https://inputs.your-instance.splunkcloud.com:8088/services/collector \
     -H "Authorization: Splunk your-hec-token" \
     -d '{"event":"test","sourcetype":"manual"}'
```

### Search in Splunk

```spl
index=mariadb_logs earliest=-1h
```

## Common Splunk Searches

> **Field names:** HEC unwraps the JSON `event` envelope, so the searchable
> fields are the top-level keys (`message`, `logType`, `server`, `service`,
> `log.level`, `serverDataSourceId`) — there is **no** `event.` prefix. Because
> `log.level` contains a dot, quote it in SPL: `` `log.level` `` or
> `'log.level'`.

### View All MariaDB Cloud Logs
```spl
index=mariadb_logs sourcetype=mariadb:logs
| table _time, logType, server, message
```

### Error Logs Only
```spl
index=mariadb_logs sourcetype=mariadb:logs logType="error-log"
| table _time, server, message
| sort -_time
```

### Logs by Server
```spl
index=mariadb_logs sourcetype=mariadb:logs
| stats count by server, logType
| sort -count
```

### MaxScale Logs
```spl
index=mariadb_logs sourcetype=mariadb:logs logType="maxscale-log"
| table _time, server, message
```

### Logs in Last Hour
```spl
index=mariadb_logs sourcetype=mariadb:logs earliest=-1h
| timechart count by logType
```

### Search for Specific Error
```spl
index=mariadb_logs sourcetype=mariadb:logs message="*error*"
| table _time, server, logType, message
```

### Log Volume by Service
```spl
index=mariadb_logs sourcetype=mariadb:logs
| timechart span=5m count by service
```

### Top 10 Servers by Log Count
```spl
index=mariadb_logs sourcetype=mariadb:logs
| stats count by server
| sort -count
| head 10
```

## Dashboard Examples

### Create a MariaDB Cloud Logs Dashboard

1. In Splunk, go to **Dashboards** > **Create New Dashboard**
2. Name it "MariaDB Cloud Logs Overview"
3. Add the following panels:

#### Panel 1: Log Volume Over Time
```spl
index=mariadb_logs sourcetype=mariadb:logs
| timechart span=5m count by logType
```

#### Panel 2: Logs by Server
```spl
index=mariadb_logs sourcetype=mariadb:logs
| stats count by server
| sort -count
```

#### Panel 3: Recent Error Logs
```spl
index=mariadb_logs sourcetype=mariadb:logs logType="error-log"
| table _time, server, message
| sort -_time
| head 20
```

#### Panel 4: Log Type Distribution
```spl
index=mariadb_logs sourcetype=mariadb:logs
| stats count by logType
```

## Alerts

### Alert on High Error Rate

```spl
index=mariadb_logs sourcetype=mariadb:logs logType="error-log"
| stats count as error_count
| where error_count > 100
```

**Trigger Condition:** Number of Results > 0
**Time Range:** Last 15 minutes
**Cron Schedule:** */15 * * * * (every 15 minutes)

### Alert on Specific Server Issues

```spl
index=mariadb_logs sourcetype=mariadb:logs server="your-server-id" message="*critical*"
| table _time, logType, message
```

**Trigger Condition:** Number of Results > 0
**Time Range:** Last 5 minutes
**Cron Schedule:** */5 * * * * (every 5 minutes)

## Troubleshooting

### No logs appearing?

1. **Run the collector manually** and read the logs it prints to stderr:
   ```bash
   python3 logs/scripts/mariadb_logs_collector.py
   ```

2. **Check the MariaDB Cloud API key:**
   ```bash
   curl -H "X-API-KEY: your-key" https://api.skysql.com/observability/v2/logs/servers
   ```

3. **Check HEC delivery** (look for `HEC authentication failed` / `HEC token disabled`
   messages in the collector output), and confirm HEC is enabled in Splunk Cloud
   and the token can write to the target index.

4. **Check Splunk-side ingestion:**
   ```spl
   index=* source=mariadb_logs_api | head 10
   index=_internal sourcetype=splunkd component=HttpEventCollector
   ```

### Duplicate or missing logs?

Dedup relies on the checkpoint file (`CHECKPOINT_FILE`). Make sure it points at a
durable path that survives restarts. Deleting it causes the collector to
re-collect from 00:00 UTC today.

### Python module not found?

```bash
pip3 install requests
```

## Advanced Configuration

### Change Polling Interval

Pass `--interval <seconds>` in daemon mode (or set it in your systemd/launchd unit):

```bash
python3 logs/scripts/mariadb_logs_collector.py --daemon --interval 600   # every 10 min
```

### Debug Logging

Pass `--verbose` to raise logging to DEBUG (e.g. per-archive dedup skip counts).
Run `python3 logs/scripts/mariadb_logs_collector.py --help` for the full option and
environment-variable reference.

### Filter Specific Log Types

Edit the `logTypes` list in `fetch_log_metadata` in `mariadb_logs_collector.py`:

```python
"logTypes": ["error-log"],   # only error logs
```

### Multiple Environments

Run separate collectors with different API keys, indexes, and checkpoint files:

```bash
SPLUNK_INDEX=mariadb_logs_prod    CHECKPOINT_FILE=/var/lib/mariadb-logs/prod.json    ... &
SPLUNK_INDEX=mariadb_logs_staging CHECKPOINT_FILE=/var/lib/mariadb-logs/staging.json ... &
```

### Field Extractions

`logs/default/props.conf` contains reference search-time field extractions for
the `mariadb:logs` sourcetype. Install that stanza on your Splunk Cloud search
head/indexer if you want them; events are JSON, so `KV_MODE=json` exposes the
event fields (`message`, `logType`, `server`, `service`, `log.level`, …) without
extra configuration.

## Support

- **MariaDB Cloud API Docs:** https://apidocs.skysql.com/
- **MariaDB Cloud Observability:** https://docs.skysql.com/Observability/
- **Splunk Docs:** https://docs.splunk.com/
