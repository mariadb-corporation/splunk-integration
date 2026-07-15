# Splunk Cloud Dashboard Examples for MariaDB Metrics

This document contains example **Dashboard Studio** (JSON) definitions for
visualizing MariaDB Cloud metrics in Splunk Cloud Platform.

> **Note:** `mariadb_metrics` is a **Metrics-type index**, so every data source
> below uses the metrics search command `mstats` (a generating command — note the
> leading `|`). Time-series panels use `mstats … span=1m BY <dim>` followed by
> `xyseries _time <dim> <value>` to produce the multi-series shape the charts
> expect. Every `mstats` search includes a `metric_name` filter, which Splunk
> requires.

> **Why JSON, not Simple XML?** Splunk Cloud's default dashboard editor is
> **Dashboard Studio**, which is JSON-based. Pasting classic Simple XML there
> fails with *"Comparator '<' is missing a term on the left hand side"* because
> the leading `<dashboard>` tag is parsed as SPL. The definitions below are
> Dashboard Studio JSON and paste cleanly into the default editor (see
> [How to Import](#how-to-import)).

## Dashboard 1: MariaDB Health Overview Report

A real-time health monitoring view of your MariaDB instances.

```json
{
  "visualizations": {
    "viz_health": {
      "type": "splunk.table",
      "dataSources": { "primary": "ds_health" },
      "title": "Database Health Overview"
    }
  },
  "dataSources": {
    "ds_health": {
      "type": "ds.search",
      "name": "Health Overview",
      "options": {
        "query": "| mstats latest(_value) as value WHERE index=mariadb_metrics AND (metric_name=\"mariadb.mariadb_server_cpu\" OR metric_name=\"mariadb.mariadb_server_memory_rss\" OR metric_name=\"mariadb.mariadb_global_status_threads_connected\" OR metric_name=\"mariadb.mariadb_global_status_uptime\") BY metric_name, server_name | eval metric_display=case(metric_name=\"mariadb.mariadb_server_cpu\", \"CPU %\", metric_name=\"mariadb.mariadb_server_memory_rss\", \"Memory (bytes)\", metric_name=\"mariadb.mariadb_global_status_threads_connected\", \"Active Connections\", metric_name=\"mariadb.mariadb_global_status_uptime\", \"Uptime (seconds)\") | chart values(value) over server_name by metric_display",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    }
  },
  "defaults": {
    "dataSources": {
      "ds.search": { "options": { "refresh": "1m", "refreshType": "delay" } }
    }
  },
  "inputs": {},
  "layout": {
    "type": "grid",
    "options": {},
    "structure": [
      { "item": "viz_health", "type": "block", "position": { "x": 0, "y": 0, "w": 1200, "h": 400 } }
    ],
    "globalInputs": []
  },
  "title": "MariaDB Health Overview Report",
  "description": "MariaDB Cloud Metrics - Health Overview"
}
```

---

## Dashboard 2: Connection Monitoring

Monitor connection usage and detect connection leaks.

```json
{
  "visualizations": {
    "viz_connections": {
      "type": "splunk.line",
      "dataSources": { "primary": "ds_connections" },
      "title": "Active Connections Over Time",
      "options": {
        "legend": { "placement": "bottom" },
        "axisTitleX": { "text": "Time" },
        "axisTitleY": { "text": "Connections" }
      }
    }
  },
  "dataSources": {
    "ds_connections": {
      "type": "ds.search",
      "name": "Connections Over Time",
      "options": {
        "query": "| mstats avg(_value) as value WHERE index=mariadb_metrics AND (metric_name=\"mariadb.mariadb_global_status_threads_connected\" OR metric_name=\"mariadb.mariadb_global_status_max_used_connections\" OR metric_name=\"mariadb.mariadb_global_variables_max_connections\") span=1m BY metric_name | xyseries _time metric_name value",
        "queryParameters": { "earliest": "-60m@m", "latest": "now" }
      }
    }
  },
  "defaults": {
    "dataSources": {
      "ds.search": { "options": { "refresh": "1m", "refreshType": "delay" } }
    }
  },
  "inputs": {},
  "layout": {
    "type": "grid",
    "options": {},
    "structure": [
      { "item": "viz_connections", "type": "block", "position": { "x": 0, "y": 0, "w": 1200, "h": 400 } }
    ],
    "globalInputs": []
  },
  "title": "MariaDB Connection Monitoring",
  "description": "Track connection usage and capacity"
}
```

---

## Dashboard 3: Query Performance

Analyze query throughput and identify slow queries.

```json
{
  "visualizations": {
    "viz_throughput": {
      "type": "splunk.line",
      "dataSources": { "primary": "ds_throughput" },
      "title": "Query Throughput",
      "options": {
        "legend": { "placement": "bottom" },
        "axisTitleX": { "text": "Time" },
        "axisTitleY": { "text": "Queries/sec" }
      }
    }
  },
  "dataSources": {
    "ds_throughput": {
      "type": "ds.search",
      "name": "Query Throughput",
      "options": {
        "query": "| mstats latest(_value) as total WHERE index=mariadb_metrics AND (metric_name=\"mariadb.mariadb_global_status_queries\" OR metric_name=\"mariadb.mariadb_global_status_slow_queries\") span=1m BY metric_name | streamstats current=f last(total) as prev_total last(_time) as prev_time BY metric_name | eval qps=round((total-prev_total)/(_time-prev_time),2) | where qps>=0 | eval series=case(metric_name=\"mariadb.mariadb_global_status_queries\", \"Queries_per_sec\", metric_name=\"mariadb.mariadb_global_status_slow_queries\", \"Slow_Queries_per_sec\") | xyseries _time series qps",
        "queryParameters": { "earliest": "-60m@m", "latest": "now" }
      }
    }
  },
  "defaults": {
    "dataSources": {
      "ds.search": { "options": { "refresh": "1m", "refreshType": "delay" } }
    }
  },
  "inputs": {},
  "layout": {
    "type": "grid",
    "options": {},
    "structure": [
      { "item": "viz_throughput", "type": "block", "position": { "x": 0, "y": 0, "w": 1200, "h": 400 } }
    ],
    "globalInputs": []
  },
  "title": "MariaDB Query Performance",
  "description": "Monitor query throughput and slow queries"
}
```

---

## Dashboard 4: Resource Utilization

Track CPU and Memory trends over time.

```json
{
  "visualizations": {
    "viz_cpu": {
      "type": "splunk.area",
      "dataSources": { "primary": "ds_cpu" },
      "title": "CPU Usage",
      "options": { "axisTitleY": { "text": "CPU %" } }
    },
    "viz_memory": {
      "type": "splunk.area",
      "dataSources": { "primary": "ds_memory" },
      "title": "Memory Usage (GB)",
      "options": { "axisTitleY": { "text": "Memory (GB)" } }
    }
  },
  "dataSources": {
    "ds_cpu": {
      "type": "ds.search",
      "name": "CPU Usage",
      "options": {
        "query": "| mstats avg(_value) as cpu WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_server_cpu\" span=1m BY server_name | xyseries _time server_name cpu",
        "queryParameters": { "earliest": "-60m@m", "latest": "now" }
      }
    },
    "ds_memory": {
      "type": "ds.search",
      "name": "Memory Usage",
      "options": {
        "query": "| mstats avg(_value) as mem_bytes WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_server_memory_rss\" span=1m BY server_name | eval mem_gb=round(mem_bytes/1024/1024/1024,2) | xyseries _time server_name mem_gb",
        "queryParameters": { "earliest": "-60m@m", "latest": "now" }
      }
    }
  },
  "defaults": {
    "dataSources": {
      "ds.search": { "options": { "refresh": "1m", "refreshType": "delay" } }
    }
  },
  "inputs": {},
  "layout": {
    "type": "grid",
    "options": {},
    "structure": [
      { "item": "viz_cpu", "type": "block", "position": { "x": 0, "y": 0, "w": 600, "h": 400 } },
      { "item": "viz_memory", "type": "block", "position": { "x": 600, "y": 0, "w": 600, "h": 400 } }
    ],
    "globalInputs": []
  },
  "title": "MariaDB Resource Utilization",
  "description": "CPU and Memory trends"
}
```

---

## Dashboard 5: Complete Monitoring Dashboard

A comprehensive dashboard combining single-value KPIs, trends, and a health table.

```json
{
  "visualizations": {
    "viz_sv_connections": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_connections" },
      "title": "Current Connections"
    },
    "viz_sv_cpu": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_cpu" },
      "title": "CPU %",
      "options": { "unit": "%" }
    },
    "viz_sv_qps": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_qps" },
      "title": "Queries per Second"
    },
    "viz_cpu_trend": {
      "type": "splunk.line",
      "dataSources": { "primary": "ds_cpu_trend" },
      "title": "CPU Usage Trend",
      "options": { "axisTitleY": { "text": "CPU %" } }
    },
    "viz_connections_trend": {
      "type": "splunk.area",
      "dataSources": { "primary": "ds_connections_trend" },
      "title": "Active Connections Trend",
      "options": { "axisTitleY": { "text": "Connections" } }
    },
    "viz_health_table": {
      "type": "splunk.table",
      "dataSources": { "primary": "ds_health_table" },
      "title": "Database Health Overview"
    }
  },
  "dataSources": {
    "ds_sv_connections": {
      "type": "ds.search",
      "name": "Current Connections",
      "options": {
        "query": "| mstats latest(_value) as connections WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_global_status_threads_connected\"",
        "queryParameters": { "earliest": "-5m@m", "latest": "now" }
      }
    },
    "ds_sv_cpu": {
      "type": "ds.search",
      "name": "CPU Usage",
      "options": {
        "query": "| mstats avg(_value) as cpu WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_server_cpu\" | eval cpu=round(cpu,1)",
        "queryParameters": { "earliest": "-5m@m", "latest": "now" }
      }
    },
    "ds_sv_qps": {
      "type": "ds.search",
      "name": "Queries per Second",
      "options": {
        "query": "| mstats latest(_value) as total WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_global_status_queries\" span=1m | streamstats current=f last(total) as prev_total last(_time) as prev_time | eval qps=round((total-prev_total)/(_time-prev_time),1) | where qps>=0 | tail 1 | fields qps",
        "queryParameters": { "earliest": "-10m@m", "latest": "now" }
      }
    },
    "ds_cpu_trend": {
      "type": "ds.search",
      "name": "CPU Usage Trend",
      "options": {
        "query": "| mstats avg(_value) as cpu WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_server_cpu\" span=1m BY server_name | xyseries _time server_name cpu",
        "queryParameters": { "earliest": "-60m@m", "latest": "now" }
      }
    },
    "ds_connections_trend": {
      "type": "ds.search",
      "name": "Active Connections Trend",
      "options": {
        "query": "| mstats avg(_value) as connections WHERE index=mariadb_metrics AND metric_name=\"mariadb.mariadb_global_status_threads_connected\" span=1m BY server_name | xyseries _time server_name connections",
        "queryParameters": { "earliest": "-60m@m", "latest": "now" }
      }
    },
    "ds_health_table": {
      "type": "ds.search",
      "name": "Health Overview",
      "options": {
        "query": "| mstats latest(_value) as value WHERE index=mariadb_metrics AND (metric_name=\"mariadb.mariadb_server_cpu\" OR metric_name=\"mariadb.mariadb_server_memory_rss\" OR metric_name=\"mariadb.mariadb_global_status_threads_connected\" OR metric_name=\"mariadb.mariadb_global_status_uptime\") BY metric_name, server_name | eval metric_display=case(metric_name=\"mariadb.mariadb_server_cpu\", \"CPU %\", metric_name=\"mariadb.mariadb_server_memory_rss\", \"Memory (bytes)\", metric_name=\"mariadb.mariadb_global_status_threads_connected\", \"Active Connections\", metric_name=\"mariadb.mariadb_global_status_uptime\", \"Uptime (seconds)\") | chart values(value) over server_name by metric_display",
        "queryParameters": { "earliest": "-5m@m", "latest": "now" }
      }
    }
  },
  "defaults": {
    "dataSources": {
      "ds.search": { "options": { "refresh": "30s", "refreshType": "delay" } }
    }
  },
  "inputs": {},
  "layout": {
    "type": "grid",
    "options": {},
    "structure": [
      { "item": "viz_sv_connections", "type": "block", "position": { "x": 0, "y": 0, "w": 400, "h": 200 } },
      { "item": "viz_sv_cpu", "type": "block", "position": { "x": 400, "y": 0, "w": 400, "h": 200 } },
      { "item": "viz_sv_qps", "type": "block", "position": { "x": 800, "y": 0, "w": 400, "h": 200 } },
      { "item": "viz_cpu_trend", "type": "block", "position": { "x": 0, "y": 200, "w": 600, "h": 300 } },
      { "item": "viz_connections_trend", "type": "block", "position": { "x": 600, "y": 200, "w": 600, "h": 300 } },
      { "item": "viz_health_table", "type": "block", "position": { "x": 0, "y": 500, "w": 1200, "h": 400 } }
    ],
    "globalInputs": []
  },
  "title": "MariaDB Cloud Complete Monitoring",
  "description": "Comprehensive MariaDB Cloud metrics monitoring"
}
```

---

## How to Import

Dashboard Studio is the default dashboard editor in Splunk Cloud Platform:

1. Log into Splunk Cloud Platform
2. Go to **Dashboards** → **Create New Dashboard**
3. Enter a title, choose **Dashboard Studio**, and pick any layout (Grid works),
   then click **Create**
4. In the editor toolbar, open the **⋮** (or **Source**) menu to reveal the JSON
   **Source** editor
5. Select all existing JSON and replace it with the definition above
6. Click **Back**/**Save**

> If you prefer Classic (Simple XML) dashboards, choose **Classic Dashboards**
> in step 3 instead — but note the JSON above is for Dashboard Studio.

## Customizing Dashboards

- **Time range:** edit each data source's `queryParameters.earliest` / `latest`
  (or add a time-range input under `inputs` and bind it).
- **Refresh rate:** edit `defaults.dataSources.ds.search.options.refresh`
  (e.g. `30s`, `1m`, `5m`).
- **Chart type:** change a visualization's `type`
  (`splunk.line`, `splunk.area`, `splunk.column`, `splunk.bar`, `splunk.table`,
  `splunk.singlevalue`).
- **Layout:** adjust each panel's `position` (`x`, `y`, `w`, `h`) in
  `layout.structure`.

## Working with a Metrics Index

- Every `mstats` search **must include at least one `metric_name` filter** in the
  `WHERE` clause — even `count`/`BY metric_name` queries. Use
  `metric_name="mariadb.*"` to match all metrics (Splunk errors with
  *"You must include at least one metric_name filter"* otherwise).
- Filter metrics by name with `metric_name="mariadb.…"` and by dimension with
  `<dimension>="…"` inside the `WHERE` clause.
- The measurement value is `_value`; aggregate it with `avg`, `sum`, `latest`,
  `rate`, etc.
- **Per-second rates (e.g. queries/sec):** avoid `mstats rate(_value)` here.
  `rate()` needs **at least two samples inside every `span` bucket**, but the
  collector polls once per 60 s, so a `span=1m` bucket holds a single sample and
  `rate()` returns nothing. Instead take `latest(_value)` per bucket for the
  cumulative counter (e.g. `mariadb.mariadb_global_status_queries`) and derive the
  rate yourself from the delta between buckets:
  ```spl
  | mstats latest(_value) as total WHERE index=mariadb_metrics AND metric_name="mariadb.mariadb_global_status_queries" span=1m
  | streamstats current=f last(total) as prev_total last(_time) as prev_time
  | eval qps=round((total-prev_total)/(_time-prev_time),2)
  | where qps>=0
  ```
  `current=f` reads the previous bucket, dividing by the real time gap yields a
  per-second value, and `where qps>=0` drops the first (null) row and any negative
  spike from a counter reset (server restart). Add `BY metric_name` (or
  `BY server_name`) to both `mstats` and `streamstats` for multiple series.
- To browse raw data points and available dimensions, use
  `| mpreview index=mariadb_metrics` or
  `| mcatalog values(metric_name) WHERE index=mariadb_metrics`.

## Available Metrics

See `metrics-list.md` for the complete list of 89 available metrics.

## Support

For more information:
- See `metrics/README.md` for integration documentation
- See `metrics/TEST_CHECKLIST.md` for verification steps
- MariaDB Cloud API: https://apidocs.skysql.com/
