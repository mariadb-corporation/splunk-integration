# Splunk Cloud Dashboard Examples for MariaDB Logs

This document contains an example **Dashboard Studio** (JSON) definition for
visualizing MariaDB Cloud logs in Splunk Cloud Platform.

> **Note:** `mariadb_logs` is a normal **events index** (unlike the metrics
> integration, which uses a metrics index). Every data source below is a
> standard event search that starts with `index=mariadb_logs
> sourcetype=mariadb:logs` and uses `stats` / `timechart` — **not** the metrics
> command `mstats`. The `log.level` field name contains a dot, so it is
> referenced with single quotes and normalized to lowercase via
> `eval level=lower('log.level')` (this also merges `Error`/`error` and
> `Warning`/`warning` across the different log types).

> **Why JSON, not Simple XML?** Splunk Cloud's default dashboard editor is
> **Dashboard Studio**, which is JSON-based. Pasting classic Simple XML there
> fails with *"Comparator '<' is missing a term on the left hand side"* because
> the leading `<dashboard>` tag is parsed as SPL. The definition below is
> Dashboard Studio JSON and pastes cleanly into the default editor (see
> [How to Import](#how-to-import)).

## Consolidated Dashboard: MariaDB Cloud Logs Monitoring

A single comprehensive view combining KPI tiles (total events, errors,
warnings, servers reporting), time trends by level and log type, distribution
and volume breakdowns, and tables of the top error messages and most recent
error/warning activity.

```json
{
  "visualizations": {
    "viz_sv_total": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_total" },
      "title": "Total Log Events"
    },
    "viz_sv_errors": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_errors" },
      "title": "Errors",
      "options": { "majorColor": "#d41f1f" }
    },
    "viz_sv_warnings": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_warnings" },
      "title": "Warnings",
      "options": { "majorColor": "#f8be34" }
    },
    "viz_sv_servers": {
      "type": "splunk.singlevalue",
      "dataSources": { "primary": "ds_sv_servers" },
      "title": "Servers Reporting"
    },
    "viz_events_by_level": {
      "type": "splunk.line",
      "dataSources": { "primary": "ds_events_by_level" },
      "title": "Log Events Over Time by Level",
      "options": {
        "legend": { "placement": "bottom" },
        "axisTitleX": { "text": "Time" },
        "axisTitleY": { "text": "Events" }
      }
    },
    "viz_events_by_type": {
      "type": "splunk.area",
      "dataSources": { "primary": "ds_events_by_type" },
      "title": "Log Events Over Time by Log Type",
      "options": {
        "legend": { "placement": "bottom" },
        "axisTitleY": { "text": "Events" },
        "stackMode": "stacked"
      }
    },
    "viz_level_distribution": {
      "type": "splunk.column",
      "dataSources": { "primary": "ds_level_distribution" },
      "title": "Event Count by Level",
      "options": { "axisTitleY": { "text": "Events" } }
    },
    "viz_volume_by_server": {
      "type": "splunk.column",
      "dataSources": { "primary": "ds_volume_by_server" },
      "title": "Event Volume by Server",
      "options": { "axisTitleY": { "text": "Events" } }
    },
    "viz_top_errors": {
      "type": "splunk.table",
      "dataSources": { "primary": "ds_top_errors" },
      "title": "Top Error Messages"
    },
    "viz_errors_by_server": {
      "type": "splunk.table",
      "dataSources": { "primary": "ds_errors_by_server" },
      "title": "Errors & Warnings by Server"
    },
    "viz_recent_events": {
      "type": "splunk.table",
      "dataSources": { "primary": "ds_recent_events" },
      "title": "Recent Errors & Warnings"
    }
  },
  "dataSources": {
    "ds_sv_total": {
      "type": "ds.search",
      "name": "Total Log Events",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | stats count as events",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_sv_errors": {
      "type": "ds.search",
      "name": "Errors",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | where level=\"error\" | stats count as errors",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_sv_warnings": {
      "type": "ds.search",
      "name": "Warnings",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | where level=\"warning\" | stats count as warnings",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_sv_servers": {
      "type": "ds.search",
      "name": "Servers Reporting",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | stats dc(server) as servers",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_events_by_level": {
      "type": "ds.search",
      "name": "Events by Level",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | timechart span=5m count by level",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_events_by_type": {
      "type": "ds.search",
      "name": "Events by Log Type",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | timechart span=5m count by logType",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_level_distribution": {
      "type": "ds.search",
      "name": "Level Distribution",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | stats count by level | sort - count",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_volume_by_server": {
      "type": "ds.search",
      "name": "Volume by Server",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | stats count by server | sort - count",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_top_errors": {
      "type": "ds.search",
      "name": "Top Error Messages",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | where level=\"error\" | stats count by message | sort - count | head 20",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_errors_by_server": {
      "type": "ds.search",
      "name": "Errors & Warnings by Server",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | where level=\"error\" OR level=\"warning\" | stats count by server, logType, level | sort - count",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    },
    "ds_recent_events": {
      "type": "ds.search",
      "name": "Recent Errors & Warnings",
      "options": {
        "query": "index=mariadb_logs sourcetype=mariadb:logs | eval level=lower('log.level') | where level=\"error\" OR level=\"warning\" | sort - _time | table _time, server, logType, level, message | head 100",
        "queryParameters": { "earliest": "-24h@h", "latest": "now" }
      }
    }
  },
  "defaults": {
    "dataSources": {
      "ds.search": { "options": { "refresh": "5m", "refreshType": "delay" } }
    }
  },
  "inputs": {},
  "layout": {
    "type": "grid",
    "options": {},
    "structure": [
      { "item": "viz_sv_total", "type": "block", "position": { "x": 0, "y": 0, "w": 300, "h": 200 } },
      { "item": "viz_sv_errors", "type": "block", "position": { "x": 300, "y": 0, "w": 300, "h": 200 } },
      { "item": "viz_sv_warnings", "type": "block", "position": { "x": 600, "y": 0, "w": 300, "h": 200 } },
      { "item": "viz_sv_servers", "type": "block", "position": { "x": 900, "y": 0, "w": 300, "h": 200 } },
      { "item": "viz_events_by_level", "type": "block", "position": { "x": 0, "y": 200, "w": 600, "h": 300 } },
      { "item": "viz_events_by_type", "type": "block", "position": { "x": 600, "y": 200, "w": 600, "h": 300 } },
      { "item": "viz_level_distribution", "type": "block", "position": { "x": 0, "y": 500, "w": 400, "h": 300 } },
      { "item": "viz_volume_by_server", "type": "block", "position": { "x": 400, "y": 500, "w": 400, "h": 300 } },
      { "item": "viz_top_errors", "type": "block", "position": { "x": 800, "y": 500, "w": 400, "h": 300 } },
      { "item": "viz_errors_by_server", "type": "block", "position": { "x": 0, "y": 800, "w": 600, "h": 350 } },
      { "item": "viz_recent_events", "type": "block", "position": { "x": 600, "y": 800, "w": 600, "h": 350 } }
    ],
    "globalInputs": []
  },
  "title": "MariaDB Cloud Logs Monitoring",
  "description": "Consolidated MariaDB Cloud logs monitoring: volume, levels, errors, and recent activity"
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
  (e.g. `1m`, `5m`, `15m`). The logs collector polls every 5 minutes by default,
  so `5m` matches the cadence at which new data arrives.
- **Chart type:** change a visualization's `type`
  (`splunk.line`, `splunk.area`, `splunk.column`, `splunk.bar`, `splunk.table`,
  `splunk.singlevalue`, `splunk.pie`).
- **Layout:** adjust each panel's `position` (`x`, `y`, `w`, `h`) in
  `layout.structure`.

## Working with the Logs (Events) Index

The collector sends each log line as a JSON HEC event to the **events** index
`mariadb_logs` with `source=mariadb_logs_api` and `sourcetype=mariadb:logs`.
Because these are events (not metrics), searches begin with
`index=mariadb_logs sourcetype=mariadb:logs` and use `search` / `stats` /
`timechart`, not `mstats`.

Fields available on each event:

| Field | Description | Example values |
|-------|-------------|----------------|
| `message` | The raw log line text | *(free text)* |
| `filename` | Source file inside the archive | `error.log`, `audit.log`, `maxscale.log` |
| `logType` | Log category | `error-log`, `audit-log`, `maxscale-log`, `slow-query-log` |
| `log.level` | Severity | `Error`/`Warning`/`Note` (error log), `error`/`warning` (MaxScale), `INFO` (audit) |
| `server` | Server name | *(per instance)* |
| `service` | Service name | *(per service)* |
| `serverDataSourceId` | Data source identifier | *(per data source)* |

- **The `log.level` field name contains a dot.** Reference it with single quotes
  (`'log.level'`) so SPL does not misparse the dot, and normalize case before
  grouping so severities merge across log types:
  ```spl
  index=mariadb_logs sourcetype=mariadb:logs
  | eval level=lower('log.level')
  | stats count by level
  ```
- **Filter by category** with `logType="error-log"` (etc.) and **by instance**
  with `server="…"` or `service="…"`.
- To browse the raw events and confirm field extraction, run
  `index=mariadb_logs sourcetype=mariadb:logs | head 20` and expand an event, or
  `index=mariadb_logs sourcetype=mariadb:logs | fieldsummary`.

### Useful standalone searches

```spl
# Error/warning rate over time, all servers
index=mariadb_logs sourcetype=mariadb:logs
| eval level=lower('log.level')
| where level="error" OR level="warning"
| timechart span=5m count by level

# Top noisy error messages in the last 24h
index=mariadb_logs sourcetype=mariadb:logs
| eval level=lower('log.level')
| where level="error"
| stats count by message
| sort - count
| head 20

# Alert: no logs received in the last 15 minutes (schedule as an alert)
index=mariadb_logs sourcetype=mariadb:logs
| stats max(_time) as last_event
| eval age=now()-last_event
| where age > 900
```

## Support

For more information:
- See `logs/QUICKSTART.md` for integration documentation
- See `logs/ARCHITECTURE.md` for how the collector parses and delivers logs
- MariaDB Cloud API: https://apidocs.skysql.com/
