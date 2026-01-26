# SkySQL Logs API - Splunk Integration Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SkySQL Cloud Platform                         │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │   MariaDB    │  │   MariaDB    │  │   MaxScale   │                │
│  │   Server 1   │  │   Server 2   │  │    Proxy     │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │
│         │                  │                  │                         │
│         └──────────────────┴──────────────────┘                         │
│                            │                                            │
│                            ▼                                            │
│                  ┌──────────────────┐                                  │
│                  │  Log Collector   │                                  │
│                  │   & Storage      │                                  │
│                  └────────┬─────────┘                                  │
│                           │                                            │
│                           ▼                                            │
│                  ┌──────────────────┐                                  │
│                  │  SkySQL Logs API │                                  │
│                  │  (REST API v2)   │                                  │
│                  └────────┬─────────┘                                  │
└───────────────────────────┼─────────────────────────────────────────────┘
                            │
                            │ HTTPS
                            │ X-API-KEY: <your-key>
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Customer Infrastructure                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │           Splunk Universal Forwarder Host                         │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Scripted Input (runs every 5 minutes)                      │ │ │
│  │  │                                                              │ │ │
│  │  │  ┌────────────────────────────────────────────────────────┐ │ │ │
│  │  │  │  skysql_logs_wrapper.sh                                │ │ │ │
│  │  │  │  • Sets environment variables                          │ │ │ │
│  │  │  │  • SKYSQL_API_KEY                                      │ │ │ │
│  │  │  │  • SKYSQL_API_URL                                      │ │ │ │
│  │  │  │  • CHECKPOINT_FILE                                     │ │ │ │
│  │  │  └──────────────────┬─────────────────────────────────────┘ │ │ │
│  │  │                     │                                        │ │ │
│  │  │                     ▼                                        │ │ │
│  │  │  ┌────────────────────────────────────────────────────────┐ │ │ │
│  │  │  │  skysql_logs_input.py                                  │ │ │ │
│  │  │  │                                                        │ │ │ │
│  │  │  │  1. Load checkpoint (last run timestamp)              │ │ │ │
│  │  │  │  2. Calculate time range (last_run to now)            │ │ │ │
│  │  │  │  3. POST to /observability/v2/logs/query              │ │ │ │
│  │  │  │     with pagination (limit=1000, offset=0...)         │ │ │ │
│  │  │  │  4. Parse JSON response                               │ │ │ │
│  │  │  │  5. Output events to stdout in JSON format            │ │ │ │
│  │  │  │  6. Save checkpoint (current timestamp)               │ │ │ │
│  │  │  │                                                        │ │ │ │
│  │  │  │  Output format:                                        │ │ │ │
│  │  │  │  {                                                     │ │ │ │
│  │  │  │    "time": "2024-01-01T12:00:00Z",                    │ │ │ │
│  │  │  │    "source": "skysql_logs_api",                       │ │ │ │
│  │  │  │    "sourcetype": "skysql:logs",                       │ │ │ │
│  │  │  │    "event": { <log data> }                            │ │ │ │
│  │  │  │  }                                                     │ │ │ │
│  │  │  └──────────────────┬─────────────────────────────────────┘ │ │ │
│  │  │                     │ stdout                                 │ │ │
│  │  └─────────────────────┼────────────────────────────────────────┘ │ │
│  │                        │                                          │ │
│  │                        ▼                                          │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Splunk Universal Forwarder                                 │ │ │
│  │  │                                                              │ │ │
│  │  │  • Captures stdout from script                             │ │ │
│  │  │  • Applies props.conf (JSON parsing, field extraction)     │ │ │
│  │  │  • Adds metadata (index, sourcetype, source)               │ │ │
│  │  │  • Forwards to indexers via TCP/9997                       │ │ │
│  │  └──────────────────┬──────────────────────────────────────────┘ │ │
│  └────────────────────┼──────────────────────────────────────────────┘ │
│                       │ TCP/9997 (compressed)                          │
└───────────────────────┼────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Splunk Infrastructure                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Splunk Indexer(s)                                                │ │
│  │                                                                   │ │
│  │  • Receives events from forwarders                               │ │
│  │  • Indexes logs in skysql_logs index                             │ │
│  │  • Stores with timestamp, metadata, and full event data          │ │
│  │  • Makes searchable via SPL (Search Processing Language)         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Splunk Search Head(s)                                            │ │
│  │                                                                   │ │
│  │  • Search interface for users                                    │ │
│  │  • Dashboards and visualizations                                 │ │
│  │  • Alerting and reporting                                        │ │
│  │  • Field extractions and data enrichment                         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Log Generation
```
MariaDB/MaxScale → Log Files → SkySQL Log Collector → SkySQL Logs API
```

### 2. API Polling (Every 5 minutes)
```
Script reads checkpoint → Calculates time range → Calls API → Receives JSON
```

### 3. Event Processing
```
Parse JSON → Format for Splunk → Output to stdout → Forwarder captures
```

### 4. Forwarding
```
Forwarder → Apply parsing rules → Add metadata → Forward to indexers
```

### 5. Indexing & Search
```
Indexer stores → Search head queries → Users search/alert/visualize
```

## Component Details

### Python Script (skysql_logs_input.py)

**Responsibilities:**
- Maintain checkpoint file to track last successful run
- Calculate appropriate time range for API query
- Handle pagination for large result sets
- Format output as JSON for Splunk consumption
- Implement rate limiting to respect API quotas
- Error handling and logging

**Key Functions:**
```python
load_checkpoint()      # Read last run timestamp
save_checkpoint()      # Save current run timestamp
fetch_log_metadata()   # Fetch log metadata from SkySQL API
fetch_log_archive()    # Download log archive
parse_log_archive()    # Parse log archive
main()                 # Orchestrate the polling process
```

**API Request Format:**
```json
POST /observability/v2/logs/query
Headers:
  X-API-KEY: <your-api-key>
  Content-Type: application/json

Body:
{
  "fromDate": "2024-01-01T00:00:00Z",
  "toDate": "2024-01-01T01:00:00Z",
  "limit": 1000,
  "offset": 0,
  "orderByField": "startTime",
  "orderByDirection": "asc"
}
```

**API Response Format:**
```json
{
  "count": 1500,
  "logs": [
    {
      "id": "123",
      "startTime": "2024-01-01T00:30:00Z",
      "logType": "error-log",
      "server": "server-1",
      "service": "service-1",
      "serverDataSourceId": "ds-123",
      "message": "Error message here",
      "filename": "error.log"
    },
    ...
  ]
}
```

### Splunk Configuration

**inputs.conf:**
```ini
[script://$SPLUNK_HOME/etc/apps/splunk-skysql-integration/scripts/skysql_logs_wrapper.sh]
disabled = false
index = skysql_logs
interval = 300
sourcetype = skysql:logs
source = skysql_logs_api
```

**props.conf:**
```ini
[skysql:logs]
SHOULD_LINEMERGE = false
KV_MODE = json
INDEXED_EXTRACTIONS = json
TIME_PREFIX = "timestamp"\s*:\s*"
TIME_FORMAT = %Y-%m-%dT%H:%M:%S.%3NZ
```

**outputs.conf:**
```ini
[tcpout]
defaultGroup = skysql_indexers

[tcpout:skysql_indexers]
server = indexer.example.com:9997
compressed = true
```

## Checkpoint Mechanism

The scripted input persists state to a JSON checkpoint file to reduce duplicate ingestion across polling cycles and restarts.

### Location / configuration

- The checkpoint path is controlled by the `CHECKPOINT_FILE` environment variable.
- Default path (if not set): `/opt/splunkforwarder/var/lib/splunk/skysql_checkpoint.json`
- The wrapper script (`scripts/skysql_logs_wrapper.sh`) typically exports `CHECKPOINT_FILE`.

### Checkpoint file format

The script stores the last queried time window plus per-log-archive progress:

┌───────────────────────────────────────────────────────────────────────────┐
│ Checkpoint file: /opt/splunkforwarder/var/lib/splunk/skysql_checkpoint.json│
│                                                                           │
│ {                                                                         │
│   "startTime": "2026-01-12T00:00:00Z",                                    │
│   "endTime":   "2026-01-12T22:34:56.123Z",                                │
│   "logs_stat": {                                                         │
│     "<log_id_1>": { "last_timestamp": "2026-01-12T22:33:01.000Z" },       │
│     "<log_id_2>": { "last_timestamp": "2026-01-12T22:33:45.000Z" }        │
│   }                                                                       │
│ }                                                                         │
└───────────────────────────────────────────────────────────────────────────┘

### How it prevents duplicates

- For each returned log archive `id`, the script downloads the zip (`/observability/v2/logs/archive`), parses individual log lines, and extracts a per-line `timestamp`.
- When parsing an archive, the script compares each line’s `timestamp` to the saved `logs_stat[log_id].last_timestamp` and **skips** lines older than the last recorded timestamp for that `log_id`.
- After processing, it updates `logs_stat[log_id].last_timestamp` to the newest timestamp seen for that archive and saves the checkpoint.

### Initial run / fallback behavior

- If the checkpoint file is missing or cannot be read, the script initializes:
  - `startTime` = **00:00:00 UTC today**
  - `endTime` = **current UTC time**
  - `logs_stat` = empty object

### Retention / pruning

- Before writing the checkpoint, the script prunes `logs_stat` entries whose `last_timestamp` is more than **2 days older than** `startTime` (to prevent unbounded growth).

### Note on time windows

- The script does **not** currently advance `startTime` as “last_run → next fromDate”. Instead, each polling cycle resets `startTime` to **00:00 UTC today** and relies on `logs_stat[log_id].last_timestamp` to avoid re-ingesting older lines within each archive.

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Security Layers                                         │
├─────────────────────────────────────────────────────────┤
│  1. API Authentication                                  │
│     • X-API-KEY header (Bearer token)                   │
│     • Keys generated in SkySQL Portal                   │
│     • Scoped permissions per key                        │
│                                                          │
│  2. Transport Security                                  │
│     • HTTPS/TLS for all API calls                       │
│     • Certificate validation                            │
│                                                          │
│  3. Credential Storage                                  │
│     • Environment variables (not in code)               │
│     • File permissions (600, owned by splunk user)      │
│     • Optional: Splunk credential storage               │
│                                                          │
│  4. Network Security                                    │
│     • Forwarder → Indexer: TCP/9997 (optionally SSL)    │
│     • Firewall rules for outbound HTTPS                 │
│                                                          │
│  5. Access Control                                      │
│     • Splunk RBAC for index access                      │
│     • Script runs as splunk user (limited privileges)   │
└─────────────────────────────────────────────────────────┘
```

## Monitoring & Observability

### What to Monitor

1. **Script Execution**
   - Check splunkd.log for script errors
   - Monitor checkpoint file updates
   - Track log ingestion rate

2. **API Health**
   - Response times
   - Error rates
   - Rate limiting events

3. **Data Freshness**
   - Time between log generation and indexing
   - Gap detection in timestamps

4. **Resource Usage**
   - Forwarder CPU/memory
   - Network bandwidth
   - Disk space for checkpoint

### Splunk Searches for Monitoring

```spl
# Script execution status
index=_internal source=*splunkd.log* skysql
| stats count by log_level

# Data ingestion rate
index=skysql_logs
| timechart span=5m count

# Data freshness (lag between log time and index time)
index=skysql_logs
| eval lag = _indextime - _time
| stats avg(lag) as avg_lag_seconds
```

## Deployment Patterns

### Single Forwarder
```
One forwarder → All SkySQL logs → One or more indexers
```
**Use Case**: Small to medium deployments, single SkySQL account

### Multiple Forwarders with Filtering
```
Forwarder 1 → Error logs only → Indexer pool
Forwarder 2 → MaxScale logs only → Indexer pool
Forwarder 3 → All other logs → Indexer pool
```
**Use Case**: High volume, need to distribute load

### Multi-Environment
```
Forwarder 1 (Prod API key) → index=skysql_prod
Forwarder 2 (Staging API key) → index=skysql_staging
Forwarder 3 (Dev API key) → index=skysql_dev
```
**Use Case**: Multiple SkySQL environments

### High Availability
```
Forwarder 1 (Primary) → Indexer cluster
Forwarder 2 (Standby) → Indexer cluster
```
**Use Case**: Mission-critical monitoring, no data loss tolerance
