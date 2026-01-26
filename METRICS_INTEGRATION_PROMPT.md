# Execution Plan: SkySQL Metrics Integration with Splunk Cloud Platform

## Project Overview
**Objective**: Create a standalone metrics integration that sends SkySQL metrics to Splunk Cloud Platform via HTTP Event Collector (HEC), completely separate from the existing logs handling infrastructure.

**Constraints**:
- Must NOT interfere with existing logs integration (`scripts/skysql_logs_input.py`, `scripts/skysql_logs_wrapper.sh`)
- Separate configuration, scripts, and documentation
- Use Splunk Cloud Platform HTTP Event Collector (HEC) for metrics ingestion
- Support both standalone execution and scheduled polling
- Compatible with Splunk Cloud free trial accounts

---

## Architecture Design

### **Data Flow**
```
SkySQL Metrics API → Metrics Polling Script → Transform to HEC Format → Splunk Cloud Platform (HEC)
```

### **Project Structure**
```
splunk-integration/
├── scripts/
│   ├── skysql_logs_input.py          # [EXISTING] Logs handling
│   ├── skysql_logs_wrapper.sh        # [EXISTING] Logs wrapper
│   ├── skysql_metrics_input.py       # [NEW] Metrics polling script
│   └── skysql_metrics_wrapper.sh     # [NEW] Metrics wrapper with env vars
├── default/
│   ├── inputs.conf                    # [EXISTING] Logs input config
│   ├── props.conf                     # [EXISTING] Logs parsing
│   └── app.conf                       # [EXISTING] App metadata
├── metrics/
│   ├── README.md                      # [NEW] Metrics integration docs
│   ├── config.yaml.example            # [NEW] Metrics config template
│   └── metrics_checkpoint.json        # [NEW] Metrics polling state
├── ARCHITECTURE.md                    # [UPDATE] Add metrics section
└── README.md                          # [UPDATE] Reference metrics integration
```

---

## Technical Specifications

### **1. Metrics API Integration**

**SkySQL Metrics Endpoint**:
- Endpoint: `https://api.skysql.com/observability/v2/metrics` (production) or `https://api-test.skysql.com/observability/v2/metrics` (test)
- Authentication: `X-Api-Key` header
- Response format: **Prometheus exposition format** (text-based, not JSON)
- Available metrics: **89 metrics total** (76 MariaDB + 13 MaxScale)

**Metric Categories**:
- Connection metrics (threads, connections, aborted clients)
- Network traffic (bytes sent/received)
- Query performance (queries, slow queries, handlers)
- InnoDB metrics (buffer pool, data read/written)
- Replication status
- CPU, memory, filesystem, network I/O
- Storage volume stats
- MaxScale proxy metrics

**Common Labels** (available on all metrics):
- `namespace` - SkySQL service namespace identifier
- `server_name` - Individual server instance identifier
- `server_type` - Server role (`server` for MariaDB, `maxscale` for MaxScale)
- `service_name` - SkySQL service name
- `topology_type` - Database topology (e.g., `standalone`, `replication`, `galera`)

**Required Capabilities**:
- Poll metrics API at configurable intervals (default: 60 seconds)
- Parse Prometheus text format response
- Convert Prometheus metrics to SignalFx datapoint format
- Extract and preserve all metric labels as dimensions
- Handle both gauge and counter metric types

### **2. Splunk Cloud Platform Integration**

**HTTP Event Collector (HEC)**:
- Endpoint: `https://inputs.prd-p-29k1h.splunkcloud.com:8088/services/collector`
- Authentication: `Authorization: Splunk <HEC-token>` header
- Format: JSON events with metric data
- Index: `main` (configured for MariaDB Cloud metrics)

**Metric Event Format**:
```json
{
  "time": 1706094000,
  "source": "mariadbl_metrics_api",
  "sourcetype": "metrics",
  "index": "main",
  "event": "metric",
  "fields": {
    "metric_name": "skysql.mariadb.cpu.usage",
    "_value": 42.5,
    "namespace": "<namespace>",
    "server_name": "server-1",
    "server_type": "server",
    "service_name": "service-1",
    "topology_type": "standalone"
  }
}
```

**Alternative: Metrics Index Format**:
```json
{
  "time": 1706094000,
  "event": "metric",
  "fields": {
    "metric_name:skysql.mariadb.cpu.usage": 42.5,
    "namespace": "<namespace>",
    "server_name": "server-1"
  }
}
```

### **3. Configuration Management**

**Environment Variables** (in `skysql_metrics_wrapper.sh`):
```bash
export SKYSQL_API_KEY="your-api-key-here"
export SKYSQL_API_URL="https://api.skysql.com"
export SPLUNK_HEC_URL="https://inputs.prd-p-29k1h.splunkcloud.com:8088"
export SPLUNK_HEC_TOKEN="your-hec-token-here"  # Token created: MariadbCloud Metrics
export SPLUNK_INDEX="main"
export SPLUNK_SOURCE="mariadbl_metrics_api"
export SPLUNK_SOURCETYPE="metrics"
export METRICS_CHECKPOINT_FILE="/var/lib/skysql/metrics_checkpoint.json"
export METRICS_POLL_INTERVAL="60"
```

**Config File** (`metrics/config.yaml`):
```yaml
skysql:
  api_url: https://api.skysql.com
  api_key: ${SKYSQL_API_KEY}
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
  checkpoint_file: /var/lib/skysql/metrics_checkpoint.json
  batch_size: 100
  
additional_fields:
  environment: production
  cluster_name: skylocalotelcluster
```

---

## Implementation Tasks

### **Phase 0: Directory Structure & Configuration Templates**

**Action**: Create directory structure and configuration template files

**Files to Create**:
- `metrics/` directory
- `metrics/config.yaml.example`
- `metrics/.gitkeep` or placeholder

**🛑 APPROVAL GATE**: Review directory structure before proceeding to Phase 1

---

### **Phase 1: Core Metrics Script**

**File**: `scripts/skysql_metrics_input.py`

**Requirements**:
1. Read configuration from environment variables
2. Implement checkpoint mechanism (track last poll timestamp)
3. Poll SkySQL Metrics API with time range
4. Parse Prometheus text format response
5. Transform metrics to HEC event format
6. Batch send to Splunk Cloud Platform HEC endpoint
7. Error handling and retry logic
8. Logging to stdout/stderr for monitoring

**Key Functions**:
- `load_checkpoint()` - Read last poll time
- `save_checkpoint(timestamp)` - Persist poll state
- `fetch_skysql_metrics()` - API call to get Prometheus-formatted metrics
- `parse_prometheus_format(text)` - Parse Prometheus text format into structured data
- `transform_to_hec_events(metrics)` - Convert Prometheus metrics to HEC event format
- `send_to_splunk_hec(events)` - Batch send to HEC endpoint
- `main()` - Orchestration

**Python Libraries Required**:
- `requests` - HTTP client for API calls
- `prometheus_client.parser` - Parse Prometheus exposition format (or custom parser)
- Standard library: `json`, `os`, `time`, `logging`

**🛑 APPROVAL GATE**: Review Python script implementation before proceeding to Phase 2

---

### **Phase 2: Wrapper Script**

**File**: `scripts/skysql_metrics_wrapper.sh`

**Requirements**:
1. Set all required environment variables
2. Execute Python script
3. Handle exit codes
4. Support both standalone and cron execution

**🛑 APPROVAL GATE**: Review wrapper script before proceeding to Phase 3

---

### **Phase 3: Metrics Documentation**

**File**: `metrics/README.md`

**Requirements**:
1. Overview and architecture
2. Prerequisites (API keys, HEC tokens)
3. Installation instructions
4. Configuration guide
5. Deployment options
6. Verification and testing
7. Troubleshooting
8. Metric catalog (list of available metrics)

**🛑 APPROVAL GATE**: Review documentation before proceeding to Phase 4

---

### **Phase 4: Project Documentation Updates**

**Files**: `README.md`, `ARCHITECTURE.md`

**Requirements**:
1. Add metrics integration section to README
2. Update ARCHITECTURE.md with metrics flow
3. Ensure clear separation from logs integration is documented

**🛑 APPROVAL GATE**: Review all changes before proceeding to testing

---

### **Phase 5: Testing & Validation**

**Requirements**:
1. Test SkySQL API connectivity
2. Test HEC endpoint connectivity
3. Verify metrics appear in Splunk Cloud Platform
4. Test checkpoint mechanism
5. Validate metric transformations

**🛑 APPROVAL GATE**: Review test results before production deployment

---

### **Phase 6: Scheduling Options (Optional)**

**Option A: Cron Job**
```bash
# /etc/cron.d/skysql-metrics
*/1 * * * * root /opt/skysql/scripts/skysql_metrics_wrapper.sh >> /var/log/skysql/metrics.log 2>&1
```

**Option B: Systemd Timer**
```ini
# /etc/systemd/system/skysql-metrics.timer
[Unit]
Description=SkySQL Metrics Collection Timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
```

**Option C: Kubernetes CronJob** (if deploying to k8s)
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: skysql-metrics-collector
spec:
  schedule: "*/1 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: metrics-collector
            image: python:3.9
            command: ["/scripts/skysql_metrics_wrapper.sh"]
```

---

## Metric Types to Collect

Based on the SkySQL Metrics API, the following 89 metrics are available in Prometheus format:

**MariaDB Metrics (76 total)**:

**Connection Metrics**:
- `mariadb_global_status_aborted_clients` - Abnormally terminated connections
- `mariadb_global_status_aborted_connects` - Failed connection attempts
- `mariadb_global_status_threads_cached` - Cached threads available for reuse
- `mariadb_global_status_threads_connected` - Active client connections
- `mariadb_global_status_threads_created` - Total threads created
- `mariadb_global_status_threads_running` - Threads actively executing queries

**Network Traffic**:
- `mariadb_global_status_bytes_received` - Total bytes received
- `mariadb_global_status_bytes_sent` - Total bytes sent

**Query Performance**:
- `mariadb_global_status_commands_total` - Command counts by type (counter)
- `mariadb_global_status_handlers_total` - Handler operation counts (counter)
- `mariadb_global_status_queries` - Total statements executed
- `mariadb_global_status_questions` - Client-sent statements
- `mariadb_global_status_slow_queries` - Slow query count

**Data Access**:
- `mariadb_global_status_rows_read` - Rows read from storage
- `mariadb_global_status_rows_sent` - Rows returned to clients

**InnoDB Metrics**:
- `mariadb_global_status_buffer_pool_pages` - Buffer pool pages by state
- `mariadb_global_status_innodb_data_read` - Bytes read by InnoDB
- `mariadb_global_status_innodb_data_written` - Bytes written by InnoDB
- `mariadb_global_status_innodb_num_open_files` - Open InnoDB files
- `mariadb_global_status_innodb_page_size` - InnoDB page size

**Resource Metrics**:
- `mariadb_server_cpu` - CPU usage percentage
- `mariadb_server_cpu_system_seconds_total` - System CPU time (counter)
- `mariadb_server_cpu_user_seconds_total` - User CPU time (counter)
- `mariadb_server_memory_cache` - Cache memory
- `mariadb_server_memory_rss` - Resident memory
- `mariadb_server_resident_memory_bytes` - Total resident memory
- `mariadb_server_virtual_memory_bytes` - Virtual memory
- `mariadb_server_spec_memory_limit_bytes` - Memory limit

**Filesystem I/O**:
- `mariadb_server_fs_reads_total` - Filesystem read operations (counter)
- `mariadb_server_fs_reads_bytes_total` - Bytes read (counter)
- `mariadb_server_fs_writes_total` - Filesystem write operations (counter)
- `mariadb_server_fs_writes_bytes_total` - Bytes written (counter)

**Network I/O**:
- `mariadb_server_network_receive_bytes_total` - Network bytes received (counter)
- `mariadb_server_network_receive_errors_total` - Receive errors (counter)
- `mariadb_server_network_transmit_bytes_total` - Network bytes sent (counter)
- `mariadb_server_network_transmit_errors_total` - Transmit errors (counter)

**Storage Volume**:
- `mariadb_server_volume_stats_available_bytes` - Available storage
- `mariadb_server_volume_stats_capacity_bytes` - Total storage capacity
- `mariadb_server_volume_stats_used_bytes` - Used storage

**Service Health**:
- `mariadb_service_server_network_status` - Network connectivity status
- `mariadb_service_server_status` - Server operational status
- `mariadb_service_status` - Overall service health
- `mariadb_up` - Database availability (1=up, 0=down)

**MaxScale Metrics (13 total)**:
- `maxscale_modules` - Loaded module information
- Connection routing and proxy metrics
- (See metrics-list.md for complete MaxScale metric details)

**Metric Labels/Dimensions**:
All metrics include these labels which become SignalFx dimensions:
- `namespace` - SkySQL service namespace
- `server_name` - Server instance identifier
- `server_type` - Server role (server/maxscale)
- `service_name` - SkySQL service name
- `topology_type` - Database topology
- Additional labels vary by metric (e.g., `command`, `handler`, `state`)

---

## Testing & Validation

### **Unit Tests**
- Checkpoint load/save
- Metric transformation
- API error handling
- Retry logic

### **Integration Tests**
1. Test SkySQL API connectivity
2. Test Splunk Observability Cloud ingest
3. Verify metrics appear in Splunk O11y UI
4. Test checkpoint recovery after failure

### **Validation Queries** (in Splunk Cloud Platform):
```spl
# View all SkySQL metrics
index=main sourcetype=metrics source=mariadbl_metrics_api
| stats count by metric_name

# CPU usage by server
index=main sourcetype=metrics metric_name="skysql.mariadb.server.cpu"
| timechart avg(_value) by server_name

# Connection count over time
index=main sourcetype=metrics metric_name="skysql.mariadb.global.status.threads.connected"
| timechart avg(_value) by service_name

# All metrics for a specific server
index=main sourcetype=metrics server_name="server-0"
| table _time, metric_name, _value, service_name

# Verify data is flowing
index=main source=mariadbl_metrics_api
| stats count latest(_time) as latest_event
```

---

## Security Considerations

1. **API Keys**: Store in environment variables, never hardcode
2. **File Permissions**: Checkpoint file should be 600, owned by service user
3. **Network**: HTTPS only for all API calls
4. **Secrets Management**: Support reading from vault/secrets manager
5. **Logging**: Never log sensitive tokens/keys

---

## Monitoring & Observability

**Script Metrics** (self-monitoring):
- Collection success/failure rate
- API response times
- Batch sizes
- Checkpoint lag (time between now and last poll)

**Alerts**:
- Collection failures > 3 consecutive runs
- API errors > 5% of requests
- Checkpoint lag > 5 minutes

---

## Rollout Plan

1. **Development**: Build and test locally
2. **Staging**: Deploy to test environment, validate metrics flow
3. **Production**: 
   - Deploy script
   - Configure scheduling
   - Monitor for 24 hours
   - Enable alerts

---

## Success Criteria

✅ Metrics successfully sent to Splunk Cloud Platform via HEC  
✅ No interference with existing logs integration  
✅ Checkpoint mechanism prevents duplicate data  
✅ Configurable and documented  
✅ Error handling and retry logic working  
✅ Metrics visible in Splunk Cloud Platform (searchable in metrics index)  
✅ Dashboards created for key metrics  
✅ Self-monitoring and alerting configured  

---

## Configuration Details

**Splunk Cloud Platform**:
- Instance: `prd-p-29k1h.splunkcloud.com`
- HEC Endpoint: `https://inputs.prd-p-29k1h.splunkcloud.com:8088/services/collector`
- HEC Token: Created (Token Name: "MariadbCloud Metrics")
- Index: `main`
- Sourcetype: `metrics`
- Source: `mariadbl_metrics_api`

**SkySQL API**:
- Base URL: `https://api.skysql.com`
- API Key: To be configured
- Metrics Endpoint: `/observability/v2/metrics`

---

## Next Steps

1. Review and validate the execution plan
2. Confirm SkySQL Metrics API endpoint and format
3. Begin Phase 1: Implement core metrics script
4. Create metrics directory structure
5. Develop and test locally
6. Deploy and validate
