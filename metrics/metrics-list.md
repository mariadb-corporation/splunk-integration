# SkySQL Observability API - Metrics Reference

This document provides a comprehensive reference for all metrics available through the MariaDB Cloud Observability API.

**API Endpoint:** `https://api.skysql.com/observability/v2/metrics`

---

## Overview

The Observability API exposes **89 metrics** in Prometheus format, providing comprehensive monitoring capabilities for your MariaDB Cloud database infrastructure:

- **76 MariaDB Metrics** - Database server performance, resource utilization, and operational status
- **13 MaxScale Metrics** - Database proxy performance and connection management

All metrics are returned in standard Prometheus exposition format and can be integrated with popular monitoring tools like Grafana, Prometheus, and Datadog.

---

## Metric Label Reference

All metrics include the following common labels for filtering and aggregation:

- **`namespace`** - Your SkySQL service namespace identifier
- **`server_name`** - Individual server instance identifier
- **`server_type`** - Server role (`server` for MariaDB, `maxscale` for MaxScale)
- **`service_name`** - Your SkySQL service name
- **`topology_type`** - Database topology configuration (e.g., `standalone`, `replication`, `galera`)

---

## MariaDB Metrics

### Connection Metrics

Monitor client connections and connection-related events.

#### `mariadb_global_status_aborted_clients`
**Type:** Gauge  
**Description:** Number of connections terminated abnormally due to client disconnection without proper connection closure.

**Example:**
```prometheus
mariadb_global_status_aborted_clients{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_aborted_connects`
**Type:** Gauge  
**Description:** Number of failed connection attempts to the database server. High values may indicate authentication issues or connection limit problems.

**Example:**
```prometheus
mariadb_global_status_aborted_connects{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_threads_cached`
**Type:** Gauge  
**Description:** Number of threads currently cached in the thread pool, available for reuse by new connections.

**Example:**
```prometheus
mariadb_global_status_threads_cached{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_threads_connected`
**Type:** Gauge  
**Description:** Current number of active client connections to the database server.

**Example:**
```prometheus
mariadb_global_status_threads_connected{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 2 1768992540899
```

#### `mariadb_global_status_threads_created`
**Type:** Gauge  
**Description:** Total number of threads created to handle client connections since server startup.

**Example:**
```prometheus
mariadb_global_status_threads_created{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 5 1768992540899
```

#### `mariadb_global_status_threads_running`
**Type:** Gauge  
**Description:** Number of threads actively executing queries (not in idle/sleep state).

**Example:**
```prometheus
mariadb_global_status_threads_running{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1 1768992540899
```

---

### Network Traffic Metrics

Track network data transfer between clients and the database server.

#### `mariadb_global_status_bytes_received`
**Type:** Gauge  
**Description:** Total bytes received from all client connections since server startup.

**Example:**
```prometheus
mariadb_global_status_bytes_received{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1234567 1768992540899
```

#### `mariadb_global_status_bytes_sent`
**Type:** Gauge  
**Description:** Total bytes sent to all client connections since server startup.

**Example:**
```prometheus
mariadb_global_status_bytes_sent{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 13673577 1768992540899
```

---

### Query Performance Metrics

Monitor query execution and database operations.

#### `mariadb_global_status_commands_total`
**Type:** Counter  
**Description:** Total count of executed commands, categorized by command type.

**Additional Labels:**
- `command` - Command type (e.g., `select`, `insert`, `update`, `delete`, `admin_commands`)

**Example:**
```prometheus
mariadb_global_status_commands_total{command="select", namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1078 1768992540899
```

#### `mariadb_global_status_handlers_total`
**Type:** Counter  
**Description:** Total count of internal storage engine handler operations.

**Additional Labels:**
- `handler` - Handler operation type (e.g., `commit`, `delete`, `read_first`, `read_key`, `write`)

**Example:**
```prometheus
mariadb_global_status_handlers_total{handler="commit", namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 612 1768992540899
```

#### `mariadb_global_status_queries`
**Type:** Gauge  
**Description:** Total number of statements executed, including those within stored procedures and triggers.

**Example:**
```prometheus
mariadb_global_status_queries{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 7898 1768992540899
```

#### `mariadb_global_status_questions`
**Type:** Gauge  
**Description:** Number of statements sent directly by clients (excludes statements executed within stored programs).

**Example:**
```prometheus
mariadb_global_status_questions{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 7881 1768992540899
```

#### `mariadb_global_status_slow_queries`
**Type:** Gauge  
**Description:** Number of queries exceeding the `long_query_time` threshold. Useful for identifying performance bottlenecks.

**Example:**
```prometheus
mariadb_global_status_slow_queries{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 571 1768992540899
```

---

### Data Access Metrics

Track row-level operations and data retrieval patterns.

#### `mariadb_global_status_rows_read`
**Type:** Gauge  
**Description:** Total number of rows read from storage engines.

**Example:**
```prometheus
mariadb_global_status_rows_read{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 11878 1768992540899
```

#### `mariadb_global_status_rows_sent`
**Type:** Gauge  
**Description:** Total number of rows returned to clients.

**Example:**
```prometheus
mariadb_global_status_rows_sent{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 166179 1768992540899
```

---

### SELECT Query Optimization Metrics

Analyze SELECT query execution patterns to identify optimization opportunities.

#### `mariadb_global_status_select_full_join`
**Type:** Gauge  
**Description:** Number of joins performing full table scans. High values indicate missing or unused indexes.

**Example:**
```prometheus
mariadb_global_status_select_full_join{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_select_full_range_join`
**Type:** Gauge  
**Description:** Number of joins using range searches on reference tables.

**Example:**
```prometheus
mariadb_global_status_select_full_range_join{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_select_range`
**Type:** Gauge  
**Description:** Number of joins using range scans on the first table.

**Example:**
```prometheus
mariadb_global_status_select_range{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 91 1768992540899
```

#### `mariadb_global_status_select_range_check`
**Type:** Gauge  
**Description:** Number of joins without indexes that evaluate key usage after each row. Indicates potential indexing issues.

**Example:**
```prometheus
mariadb_global_status_select_range_check{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_select_scan`
**Type:** Gauge  
**Description:** Number of joins performing full table scans on the first table.

**Example:**
```prometheus
mariadb_global_status_select_scan{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 5892 1768992540899
```

---

### Sort Operation Metrics

Monitor sorting operations and temporary table usage.

#### `mariadb_global_status_sort_merge_passes`
**Type:** Gauge  
**Description:** Number of merge passes required by the sort algorithm. High values may indicate insufficient sort buffer size.

**Example:**
```prometheus
mariadb_global_status_sort_merge_passes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_sort_range`
**Type:** Gauge  
**Description:** Number of sorts performed using range scans.

**Example:**
```prometheus
mariadb_global_status_sort_range{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_sort_rows`
**Type:** Gauge  
**Description:** Total number of rows sorted.

**Example:**
```prometheus
mariadb_global_status_sort_rows{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_sort_scan`
**Type:** Gauge  
**Description:** Number of sorts performed using full table scans.

**Example:**
```prometheus
mariadb_global_status_sort_scan{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

---

### InnoDB Storage Engine Metrics

Monitor InnoDB buffer pool and data operations.

#### `mariadb_global_status_buffer_pool_pages`
**Type:** Gauge  
**Description:** InnoDB buffer pool pages categorized by state.

**Additional Labels:**
- `state` - Page state (`data`, `free`, `misc`, `dirty`)

**Example:**
```prometheus
mariadb_global_status_buffer_pool_pages{state="data", namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 159 1768992540899
```

#### `mariadb_global_status_innodb_data_read`
**Type:** Gauge  
**Description:** Total bytes read by InnoDB storage engine.

**Example:**
```prometheus
mariadb_global_status_innodb_data_read{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 2605056 1768992540899
```

#### `mariadb_global_status_innodb_data_written`
**Type:** Gauge  
**Description:** Total bytes written by InnoDB storage engine.

**Example:**
```prometheus
mariadb_global_status_innodb_data_written{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_innodb_num_open_files`
**Type:** Gauge  
**Description:** Number of files currently held open by InnoDB.

**Example:**
```prometheus
mariadb_global_status_innodb_num_open_files{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 12 1768992540899
```

#### `mariadb_global_status_innodb_page_size`
**Type:** Gauge  
**Description:** InnoDB page size in bytes (typically 16384 bytes).

**Example:**
```prometheus
mariadb_global_status_innodb_page_size{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 16384 1768992540899
```

---

### Table and File Metrics

Monitor table cache performance and file operations.

#### `mariadb_global_status_open_files`
**Type:** Gauge  
**Description:** Current number of open files.

**Example:**
```prometheus
mariadb_global_status_open_files{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 32 1768992540899
```

#### `mariadb_global_status_open_table_definitions`
**Type:** Gauge  
**Description:** Number of table definitions currently cached in memory.

**Example:**
```prometheus
mariadb_global_status_open_table_definitions{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 15 1768992540899
```

#### `mariadb_global_status_open_tables`
**Type:** Gauge  
**Description:** Current number of open tables.

**Example:**
```prometheus
mariadb_global_status_open_tables{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 15 1768992540899
```

#### `mariadb_global_status_opened_files`
**Type:** Gauge  
**Description:** Total number of files opened since server startup.

**Example:**
```prometheus
mariadb_global_status_opened_files{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 986 1768992540899
```

#### `mariadb_global_status_opened_table_definitions`
**Type:** Gauge  
**Description:** Total number of table definitions cached since server startup.

**Example:**
```prometheus
mariadb_global_status_opened_table_definitions{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 51 1768992540899
```

#### `mariadb_global_status_opened_tables`
**Type:** Gauge  
**Description:** Total number of tables opened since server startup.

**Example:**
```prometheus
mariadb_global_status_opened_tables{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 48 1768992540899
```

#### `mariadb_global_status_table_locks_immediate`
**Type:** Gauge  
**Description:** Number of table locks acquired immediately without waiting.

**Example:**
```prometheus
mariadb_global_status_table_locks_immediate{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 634 1768992540899
```

#### `mariadb_global_status_table_locks_waited`
**Type:** Gauge  
**Description:** Number of table locks that required waiting. High values indicate lock contention.

**Example:**
```prometheus
mariadb_global_status_table_locks_waited{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_status_table_open_cache_hits`
**Type:** Gauge  
**Description:** Number of successful table cache lookups.

**Example:**
```prometheus
mariadb_global_status_table_open_cache_hits{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1234 1768992540899
```

#### `mariadb_global_status_table_open_cache_misses`
**Type:** Gauge  
**Description:** Number of table cache lookups that required opening the table. High values may indicate insufficient table cache size.

**Example:**
```prometheus
mariadb_global_status_table_open_cache_misses{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 48 1768992540899
```

#### `mariadb_global_status_table_open_cache_overflows`
**Type:** Gauge  
**Description:** Number of table cache overflows. Indicates table cache is too small.

**Example:**
```prometheus
mariadb_global_status_table_open_cache_overflows{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

---

### Replication Metrics

Monitor replication status for replica servers.

#### `mariadb_global_status_slave_running`
**Type:** Gauge  
**Description:** Replication status indicator (1 = replication active, 0 = replication stopped).

**Example:**
```prometheus
mariadb_global_status_slave_running{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

---

### System Status Metrics

Track server uptime and availability.

#### `mariadb_global_status_uptime`
**Type:** Gauge  
**Description:** Server uptime in seconds since last restart.

**Example:**
```prometheus
mariadb_global_status_uptime{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 86400 1768992540899
```

---

### Configuration Variables

Monitor key database configuration parameters.

#### `mariadb_global_variables_gtid_current_pos`
**Type:** Gauge  
**Description:** Current Global Transaction ID (GTID) position for replication tracking.

**Example:**
```prometheus
mariadb_global_variables_gtid_current_pos{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_variables_innodb_buffer_pool_size`
**Type:** Gauge  
**Description:** Configured InnoDB buffer pool size in bytes.

**Example:**
```prometheus
mariadb_global_variables_innodb_buffer_pool_size{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 134217728 1768992540899
```

#### `mariadb_global_variables_innodb_log_buffer_size`
**Type:** Gauge  
**Description:** Configured InnoDB log buffer size in bytes.

**Example:**
```prometheus
mariadb_global_variables_innodb_log_buffer_size{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 16777216 1768992540899
```

#### `mariadb_global_variables_key_buffer_size`
**Type:** Gauge  
**Description:** Configured MyISAM key buffer size in bytes.

**Example:**
```prometheus
mariadb_global_variables_key_buffer_size{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 134217728 1768992540899
```

#### `mariadb_global_variables_max_connections`
**Type:** Gauge  
**Description:** Maximum allowed simultaneous client connections.

**Example:**
```prometheus
mariadb_global_variables_max_connections{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 151 1768992540899
```

#### `mariadb_global_variables_open_files_limit`
**Type:** Gauge  
**Description:** Operating system limit on open file descriptors.

**Example:**
```prometheus
mariadb_global_variables_open_files_limit{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 32768 1768992540899
```

#### `mariadb_global_variables_query_cache_size`
**Type:** Gauge  
**Description:** Configured query cache size in bytes (0 = disabled).

**Example:**
```prometheus
mariadb_global_variables_query_cache_size{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_variables_read_only`
**Type:** Gauge  
**Description:** Read-only mode status (1 = read-only enabled, 0 = read-write mode).

**Example:**
```prometheus
mariadb_global_variables_read_only{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_global_variables_table_open_cache`
**Type:** Gauge  
**Description:** Configured table cache size for all threads.

**Example:**
```prometheus
mariadb_global_variables_table_open_cache{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 2000 1768992540899
```

---

### Security Metrics

Monitor database security configuration.

#### `mariadb_security_users_without_passwords`
**Type:** Gauge  
**Description:** Number of database user accounts configured without passwords. Should be zero for production systems.

**Example:**
```prometheus
mariadb_security_users_without_passwords{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

---

### CPU Resource Metrics

Monitor CPU utilization and processing time.

#### `mariadb_server_cpu`
**Type:** Gauge  
**Description:** Current CPU usage as a percentage (0.0 to 1.0 scale).

**Example:**
```prometheus
mariadb_server_cpu{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0.05 1768992540899
```

#### `mariadb_server_cpu_system_seconds_total`
**Type:** Counter  
**Description:** Cumulative CPU time spent in kernel/system mode.

**Example:**
```prometheus
mariadb_server_cpu_system_seconds_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 123.45 1768992540899
```

#### `mariadb_server_cpu_user_seconds_total`
**Type:** Counter  
**Description:** Cumulative CPU time spent in user mode executing database operations.

**Example:**
```prometheus
mariadb_server_cpu_user_seconds_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 456.78 1768992540899
```

#### `mariadb_server_spec_cpu_period`
**Type:** Gauge  
**Description:** CPU scheduling period for the container (CFS scheduler configuration).

**Example:**
```prometheus
mariadb_server_spec_cpu_period{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 100000 1768992540899
```

---

### Memory Resource Metrics

Track memory allocation and usage patterns.

#### `mariadb_server_memory_cache`
**Type:** Gauge  
**Description:** Memory allocated for caching purposes.

**Example:**
```prometheus
mariadb_server_memory_cache{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 12345678 1768992540899
```

#### `mariadb_server_memory_rss`
**Type:** Gauge  
**Description:** Resident Set Size - physical memory currently allocated in RAM.

**Example:**
```prometheus
mariadb_server_memory_rss{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 234567890 1768992540899
```

#### `mariadb_server_resident_memory_bytes`
**Type:** Gauge  
**Description:** Total resident memory usage in bytes.

**Example:**
```prometheus
mariadb_server_resident_memory_bytes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 234567890 1768992540899
```

#### `mariadb_server_virtual_memory_bytes`
**Type:** Gauge  
**Description:** Total virtual memory allocated (includes swap and reserved memory).

**Example:**
```prometheus
mariadb_server_virtual_memory_bytes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1234567890 1768992540899
```

#### `mariadb_server_spec_memory_limit_bytes`
**Type:** Gauge  
**Description:** Configured memory limit for the database container.

**Example:**
```prometheus
mariadb_server_spec_memory_limit_bytes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 2147483648 1768992540899
```

---

### Filesystem I/O Metrics

Monitor disk read and write operations.

#### `mariadb_server_fs_reads_total`
**Type:** Counter  
**Description:** Total number of filesystem read operations performed.

**Example:**
```prometheus
mariadb_server_fs_reads_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 12345 1768992540899
```

#### `mariadb_server_fs_reads_bytes_total`
**Type:** Counter  
**Description:** Total bytes read from the filesystem.

**Example:**
```prometheus
mariadb_server_fs_reads_bytes_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 123456789 1768992540899
```

#### `mariadb_server_fs_writes_total`
**Type:** Counter  
**Description:** Total number of filesystem write operations performed.

**Example:**
```prometheus
mariadb_server_fs_writes_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 6789 1768992540899
```

#### `mariadb_server_fs_writes_bytes_total`
**Type:** Counter  
**Description:** Total bytes written to the filesystem.

**Example:**
```prometheus
mariadb_server_fs_writes_bytes_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 67890123 1768992540899
```

---

### Network I/O Metrics

Monitor network traffic and errors at the container level.

#### `mariadb_server_network_receive_bytes_total`
**Type:** Counter  
**Description:** Total bytes received over the network interface.

**Example:**
```prometheus
mariadb_server_network_receive_bytes_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 123456789 1768992540899
```

#### `mariadb_server_network_receive_errors_total`
**Type:** Counter  
**Description:** Total network receive errors encountered.

**Example:**
```prometheus
mariadb_server_network_receive_errors_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_server_network_receive_packets_dropped_total`
**Type:** Counter  
**Description:** Total incoming network packets dropped.

**Example:**
```prometheus
mariadb_server_network_receive_packets_dropped_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_server_network_transmit_bytes_total`
**Type:** Counter  
**Description:** Total bytes transmitted over the network interface.

**Example:**
```prometheus
mariadb_server_network_transmit_bytes_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 987654321 1768992540899
```

#### `mariadb_server_network_transmit_errors_total`
**Type:** Counter  
**Description:** Total network transmit errors encountered.

**Example:**
```prometheus
mariadb_server_network_transmit_errors_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

#### `mariadb_server_network_transmit_packets_dropped_total`
**Type:** Counter  
**Description:** Total outgoing network packets dropped.

**Example:**
```prometheus
mariadb_server_network_transmit_packets_dropped_total{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 0 1768992540899
```

---

### Storage Volume Metrics

Monitor persistent storage capacity and utilization.

#### `mariadb_server_volume_stats_available_bytes`
**Type:** Gauge  
**Description:** Available storage space remaining on the data volume.

**Example:**
```prometheus
mariadb_server_volume_stats_available_bytes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 50000000000 1768992540899
```

#### `mariadb_server_volume_stats_capacity_bytes`
**Type:** Gauge  
**Description:** Total storage capacity of the data volume.

**Example:**
```prometheus
mariadb_server_volume_stats_capacity_bytes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 107374182400 1768992540899
```

#### `mariadb_server_volume_stats_used_bytes`
**Type:** Gauge  
**Description:** Storage space currently in use on the data volume.

**Example:**
```prometheus
mariadb_server_volume_stats_used_bytes{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 57374182400 1768992540899
```

---

### Service Health Metrics

Monitor overall service and server health status.

#### `mariadb_service_server_network_status`
**Type:** Gauge  
**Description:** Network connectivity status for the server (1 = reachable, 0 = unreachable).

**Example:**
```prometheus
mariadb_service_server_network_status{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1 1768992540899
```

#### `mariadb_service_server_status`
**Type:** Gauge  
**Description:** Overall server operational status within the service.

**Example:**
```prometheus
mariadb_service_server_status{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1 1768992540899
```

#### `mariadb_service_status`
**Type:** Gauge  
**Description:** Overall service health status (1 = healthy, 0 = unhealthy).

**Example:**
```prometheus
mariadb_service_status{namespace="<namespace>", service_name="<service>", topology_type="<topology>"} 1 1768992540899
```

#### `mariadb_up`
**Type:** Gauge  
**Description:** Database server availability indicator (1 = running, 0 = down).

**Example:**
```prometheus
mariadb_up{namespace="<namespace>", server_name="<server-0>", server_type="server", service_name="<service>", topology_type="<topology>"} 1 1768992540899
```

---

## MaxScale Metrics

MaxScale is the intelligent database proxy that routes queries and manages connections between your applications and MariaDB servers.

### Module Information

#### `maxscale_modules`
**Type:** Gauge  
**Description:** Information about loaded MaxScale modules and their versions. Each module provides specific functionality (authentication, filtering, monitoring, routing, etc.).

**Additional Labels:**
- `module_name` - Module identifier
- `module_type` - Module category (Authenticator, Filter, Monitor, Protocol, Parser, Router)
- `version` - Module version

**Available Module Types:**
- **Authenticators** - Handle client authentication (GSSAPI, MariaDB, PAM)
- **Filters** - Process and transform queries (cache, comment, ccrfilter)
- **Monitors** - Track backend server health (csmon, galeramon, mariadbmon)
- **Protocols** - Manage client-server communication (CDC, mariadbclient)
- **Parsers** - Parse SQL statements (pp_sqlite)
- **Routers** - Direct queries to appropriate servers (readconnroute, readwritesplit)

**Example:**
```prometheus
maxscale_modules{module_name="galeramon", module_type="Monitor", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>", version="V2.0.0"} 1 1768992291891
```

---

### Connection Metrics

#### `maxscale_server_connections`
**Type:** Gauge  
**Description:** Current number of connections from MaxScale to each backend database server.

**Additional Labels:**
- `id` - Backend server identifier

**Example:**
```prometheus
maxscale_server_connections{id="<server-0>", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 0 1768992291891
```

#### `maxscale_service_connections`
**Type:** Gauge  
**Description:** Current number of client connections to each MaxScale service endpoint.

**Additional Labels:**
- `id` - Service endpoint identifier

**Common Service Types:**
- **Read-Write Service** - Handles both read and write operations
- **Read-Only Service** - Routes read-only queries to replicas
- **NoSQL Service** - Provides NoSQL protocol access
- **Insecure-RW Service** - Read-write service without SSL/TLS

**Example:**
```prometheus
maxscale_service_connections{id="Read-Write-Service", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 0 1768992291891
```

---

### Thread Performance Metrics

MaxScale uses worker threads to handle client connections and backend communication.

#### `maxscale_threads_count`
**Type:** Gauge  
**Description:** Total number of worker threads configured in MaxScale.

**Example:**
```prometheus
maxscale_threads_count{namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 2 1768992291891
```

#### `maxscale_threads_current_descriptors`
**Type:** Gauge  
**Description:** Number of file descriptors currently in use by each worker thread.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_current_descriptors{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 7 1768992291891
```

#### `maxscale_threads_errors`
**Type:** Counter  
**Description:** Total number of errors encountered by each worker thread.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_errors{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 0 1768992291891
```

#### `maxscale_threads_event_queue_length`
**Type:** Gauge  
**Description:** Current number of events waiting in each thread's event queue.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_event_queue_length{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 0 1768992291891
```

#### `maxscale_threads_hangups`
**Type:** Counter  
**Description:** Total number of connection terminations (hangups) handled by each thread.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_hangups{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 477 1768992291891
```

#### `maxscale_threads_max_queue_time`
**Type:** Gauge  
**Description:** Maximum time (milliseconds) an event spent waiting in the queue before processing.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_max_queue_time{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 0 1768992291891
```

#### `maxscale_threads_reads`
**Type:** Counter  
**Description:** Total number of read operations performed by each worker thread.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_reads{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 15523 1768992291891
```

#### `maxscale_threads_stack_size`
**Type:** Gauge  
**Description:** Configured stack size for worker threads (in bytes).

**Example:**
```prometheus
maxscale_threads_stack_size{namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 0 1768992291891
```

#### `maxscale_threads_total_descriptors`
**Type:** Gauge  
**Description:** Total number of file descriptors that have been used by each thread since startup.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_total_descriptors{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 508 1768992291891
```

#### `maxscale_threads_writes`
**Type:** Counter  
**Description:** Total number of write operations performed by each worker thread.

**Additional Labels:**
- `id` - Thread identifier

**Example:**
```prometheus
maxscale_threads_writes{id="0", namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 623 1768992291891
```

---

### System Status

#### `maxscale_up`
**Type:** Gauge  
**Description:** MaxScale availability indicator (1 = running, 0 = down).

**Example:**
```prometheus
maxscale_up{namespace="<namespace>", server_name="<proxy-0>", server_type="maxscale", service_name="<service>", topology_type="<topology>"} 1 1768992291891
```

---

## Prometheus Format Reference

All metrics follow the Prometheus exposition format:

```prometheus
# TYPE <metric_name> <metric_type>
<metric_name>{label1="value1", label2="value2", ...} <value> <timestamp_ms>
```

**Components:**
- **Metric Name** - Identifies the measurement
- **Metric Type** - Either `gauge` (point-in-time value) or `counter` (cumulative value)
- **Labels** - Key-value pairs for filtering and aggregation
- **Value** - The numeric measurement
- **Timestamp** - Unix timestamp in milliseconds

---

## Integration Examples

### Prometheus Configuration

```yaml
scrape_configs:
  - job_name: 'skysql-metrics'
    metrics_path: '/observability/v2/metrics'
    scheme: https
    static_configs:
      - targets: ['api.skysql.com']
    bearer_token: 'your-api-key'
    scrape_interval: 30s
```

### Grafana Dashboard Query Examples

**Active Connections:**
```promql
mariadb_global_status_threads_connected{service_name="<your-service>"}
```

**Query Rate:**
```promql
rate(mariadb_global_status_queries{service_name="<your-service>"}[5m])
```

**Buffer Pool Hit Ratio:**
```promql
(mariadb_global_status_table_open_cache_hits / 
 (mariadb_global_status_table_open_cache_hits + mariadb_global_status_table_open_cache_misses)) * 100
```

**Disk Usage Percentage:**
```promql
(mariadb_server_volume_stats_used_bytes / mariadb_server_volume_stats_capacity_bytes) * 100
```

---

## Metric Summary

**Total Metrics:** 89

### MariaDB Metrics (76)
- **Connection Metrics:** 6
- **Network Traffic:** 2
- **Query Performance:** 6
- **Data Access:** 2
- **SELECT Optimization:** 5
- **Sort Operations:** 4
- **InnoDB Storage:** 5
- **Table & File Operations:** 11
- **Replication:** 1
- **System Status:** 1
- **Configuration Variables:** 9
- **Security:** 1
- **CPU Resources:** 4
- **Memory Resources:** 5
- **Filesystem I/O:** 4
- **Network I/O:** 6
- **Storage Volumes:** 3
- **Service Health:** 4

### MaxScale Metrics (13)
- **Module Information:** 1
- **Connection Management:** 2
- **Thread Performance:** 9
- **System Status:** 1

---

## Support

For additional assistance with the Observability API or metric interpretation, please contact SkySQL Support or refer to the [SkySQL Documentation](https://mariadb.com/docs/skysql/).
