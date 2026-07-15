# MariaDB Cloud Logs API - Splunk Integration Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MariaDB Cloud Platform                        │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   MariaDB    │  │   MariaDB    │  │   MaxScale   │                   │
│  │   Server 1   │  │   Server 2   │  │    Proxy     │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         └──────────────────┴──────────────────┘                         │
│                            ▼                                            │
│                  ┌──────────────────┐                                   │
│                  │ MariaDB Logs API │  (REST API v2)                    │
│                  └────────┬─────────┘                                   │
└───────────────────────────┼─────────────────────────────────────────────┘
                            │ HTTPS  (X-API-KEY: <your-key>)
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Collector Host (VM / container / pod)                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  mariadb_logs_collector.py  (MariaDBLogsCollector)                │  │
│  │                                                                   │  │
│  │  1. Load checkpoint (per-archive last_timestamp)                  │  │
│  │  2. POST /observability/v2/logs/query   (metadata, paginated)     │  │
│  │  3. GET  /observability/v2/logs/archive (download zip per log)    │  │
│  │  4. Parse lines, skip those <= checkpoint (dedup)                 │  │
│  │  5. Transform each line → Splunk HEC event                        │  │
│  │  6. POST batches → Splunk HEC /services/collector                 │  │
│  │  7. Save checkpoint per archive (after that archive is sent)      │  │
│  │                                                                   │  │
│  │  Run modes: once (default) or --daemon --interval N               │  │
│  └──────────────────┬────────────────────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────────────────────┘
                      │ HTTPS  (Authorization: Splunk <hec-token>)
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Splunk Cloud Platform                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  HTTP Event Collector (HEC)                                       │  │
│  │  • Receives JSON events, routes to the target index (mariadb_logs)│  │
│  │  • Applies sourcetype (mariadb:logs) parsing / field extractions  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Search Heads: SPL search, dashboards, alerting                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Log Generation** — MariaDB/MaxScale → MariaDB Cloud Log Collector → MariaDB Cloud Logs API.
2. **Polling** — the collector loads its checkpoint, queries log metadata for the time window (00:00 UTC today → now), and downloads each log archive.
3. **Parse & Dedup** — each archive (zip) is unpacked; lines older than the archive's saved `last_timestamp` are skipped.
4. **Transform** — each remaining line becomes a Splunk HEC event `{time, source, sourcetype, index, event:{...}}`.
5. **Send** — each archive's events are POSTed to the Splunk HEC endpoint in batches, with retry/backoff.
6. **Checkpoint** — the checkpoint is written **per archive**, immediately after that archive's events are delivered (advancing its `last_timestamp`). A mid-cycle send failure stops the cycle without re-sending archives already delivered this cycle.
7. **Index & Search** — HEC ingests to the target index; users search/alert/visualize via SPL.

## Component Details

### Python Script (`mariadb_logs_collector.py`)

The `MariaDBLogsCollector` class encapsulates all behavior. Key methods:

```python
load_checkpoint() / save_checkpoint()    # per-archive dedup state
fetch_servers()                          # serverContext for the query
fetch_log_metadata()                     # POST /observability/v2/logs/query
fetch_log_archive()                      # GET  /observability/v2/logs/archive
parse_log_archive()                      # unzip + per-line parse + dedup skip
transform_to_hec_events()                # log line → HEC event dict
send_to_splunk_hec()                     # batched POST to HEC with retry
run()                                    # one collection cycle
run_daemon()                             # continuous polling + graceful shutdown
```

**Diagnostics** go to the `logging` module (stderr). Unlike the previous
forwarder-based design, **stdout is not a data channel** — events travel over
HTTP to HEC.

**API request format** (`POST /observability/v2/logs/query`):
```json
{
  "fromDate": "2026-01-12T00:00:00Z",
  "toDate": "2026-01-12T22:34:56Z",
  "limit": 100,
  "offset": 0,
  "logTypes": ["error-log", "audit-log", "maxscale-log"],
  "orderByField": "startTime",
  "orderByDirection": "asc",
  "serverContext": ["<serverDataSourceId>", "..."]
}
```

**HEC event format** (one per log line):
```json
{
  "time": 1767916800.123,
  "source": "mariadb_logs_api",
  "sourcetype": "mariadb:logs",
  "index": "mariadb_logs",
  "event": {
    "message": "...",
    "filename": "error.log",
    "logType": "error-log",
    "log.level": "Warning",
    "server": "server-1",
    "service": "service-1",
    "serverDataSourceId": "ds-123"
  }
}
```
The HEC `time` field is **epoch seconds**, converted from each line's ISO-8601
timestamp (fractional seconds beyond microseconds, e.g. MaxScale nanoseconds,
are truncated).

### Splunk-side configuration

Because there is no forwarder, index-time/search-time field extractions must be
configured on the Splunk Cloud side. `logs/default/props.conf` is kept in the
repo **as a reference** — install its `[mariadb:logs]` stanza on the search
head/indexer if you want the field extractions. Events are JSON, so `KV_MODE`
makes the fields available without extra configuration. Note that HEC unwraps
the `event` envelope, so the extracted fields are the top-level keys
(`message`, `logType`, `server`, …) — there is **no** `event.` prefix in SPL.

## Checkpoint Mechanism

The collector persists state to a JSON checkpoint file to avoid re-ingesting
log lines across polling cycles and restarts.

### Location / configuration

- Path is controlled by the `CHECKPOINT_FILE` environment variable.
- Default: `./mariadb_checkpoint.json` (point it at a durable path in production,
  e.g. `/var/lib/mariadb-logs/mariadb_checkpoint.json` or a mounted volume).

### Checkpoint file format

```json
{
  "startTime": "2026-01-12T00:00:00Z",
  "endTime":   "2026-01-12T22:34:56.123Z",
  "logs_stat": {
    "<log_id_1>": { "last_timestamp": "2026-01-12T22:33:01.000Z" },
    "<log_id_2>": { "last_timestamp": "2026-01-12T22:33:45.000Z" }
  }
}
```

### How it prevents duplicates

- For each archive `id`, `parse_log_archive` extracts a per-line `timestamp` and
  **skips** lines strictly older than the seed `logs_stat[id].last_timestamp`.
  The seed is treated as immutable during parsing; the new value returned is the
  **maximum** timestamp seen (not the last line processed), so out-of-order lines
  are not dropped. Lines with no parseable timestamp inherit the previous line's.
- The checkpoint is written **per archive**, immediately after that archive's
  events are delivered to HEC, so a mid-cycle failure is retried on the next
  cycle without re-sending already-delivered archives (at-least-once delivery).
  The boundary line (timestamp equal to the seed) may be re-sent.

### Retention / pruning

- Before writing, `save_checkpoint` prunes `logs_stat` entries whose
  `last_timestamp` is more than **2 days older** than `startTime`.

### Note on time windows

- Each cycle resets `startTime` to **00:00 UTC today** rather than advancing a
  sliding window; dedup relies on `logs_stat[log_id].last_timestamp`.

## Deployment Patterns

Run the collector as a persistent daemon (`--daemon --interval N`) managed by
systemd, launchd, or Kubernetes. See [`examples/`](examples/) for ready-to-use
configurations.

- **Single collector** → all MariaDB Cloud logs → one Splunk Cloud index. Keep a
  single instance per checkpoint so the file is not written concurrently.
- **Multi-environment** → run separate collectors with different API keys and
  `SPLUNK_INDEX`/`CHECKPOINT_FILE` values (e.g. prod/staging/dev).

## Monitoring & Observability

Monitor the collector process logs (stderr / journald / pod logs) and data
freshness in Splunk:

```spl
# Data ingestion rate
index=mariadb_logs sourcetype=mariadb:logs
| timechart span=5m count

# Data freshness (lag between log time and index time)
index=mariadb_logs sourcetype=mariadb:logs
| eval lag = _indextime - _time
| stats avg(lag) as avg_lag_seconds

# HEC health (Splunk internal)
index=_internal sourcetype=splunkd component=HttpEventCollector
```

## Security Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Security Layers                                               │
├────────────────────────────────────────────────────────────────┤
│  1. MariaDB Cloud API Authentication                           │
│     • X-API-KEY header; keys scoped in the MariaDB Cloud Portal│
│  2. Splunk HEC Authentication                                  │
│     • Authorization: Splunk <token>; scoped to an index        │
│  3. Transport Security                                         │
│     • HTTPS/TLS for both API and HEC calls                     │
│     • SPLUNK_HEC_VERIFY_SSL controls HEC cert validation       │
│  4. Credential Storage                                         │
│     • Environment variables / secrets (not in code)            │
│  5. Access Control                                             │
│     • Splunk RBAC for index access                             │
└────────────────────────────────────────────────────────────────┘
```
