# Splunk Cloud Dashboard Examples for MariaDB Metrics

This document contains example dashboard XML configurations for visualizing MariaDB Cloud metrics in Splunk Cloud Platform.

## Dashboard 1: MariaDB Health Overview Report

This dashboard provides a real-time health monitoring view of your MariaDB instances.

### Dashboard XML

```xml
<dashboard version="1.1" theme="light">
  <label>MariaDB Health Overview Report</label>
  <description>MariaDB Cloud Metrics - Health Overview</description>
  <row>
    <panel>
      <title>Database Health Overview</title>
      <table>
        <search>
          <query>index=main sourcetype=metrics 
    (metric_name="mariadb.mariadb_server_cpu" OR 
     metric_name="mariadb.mariadb_server_memory_rss" OR 
     metric_name="mariadb.mariadb_global_status_threads_connected" OR
     metric_name="mariadb.mariadb_global_status_uptime")
| stats latest(_value) as value by metric_name, server_name
| eval metric_display=case(
    metric_name="mariadb.mariadb_server_cpu", "CPU %",
    metric_name="mariadb.mariadb_server_memory_rss", "Memory (bytes)",
    metric_name="mariadb.mariadb_global_status_threads_connected", "Active Connections",
    metric_name="mariadb.mariadb_global_status_uptime", "Uptime (seconds)"
)
| chart values(value) over server_name by metric_display</query>
          <earliest>-24h@h</earliest>
          <latest>now</latest>
          <sampleRatio>1</sampleRatio>
          <refresh>1m</refresh>
        </search>
        <option name="count">20</option>
        <option name="dataOverlayMode">none</option>
        <option name="drilldown">none</option>
        <option name="percentagesRow">false</option>
        <option name="refresh.display">progressbar</option>
        <option name="rowNumbers">false</option>
        <option name="totalsRow">false</option>
        <option name="wrap">true</option>
      </table>
    </panel>
  </row>
</dashboard>
```

### How to Import

1. Log into Splunk Cloud Platform
2. Go to **Settings** → **User Interface** → **Dashboards**
3. Click **Create New Dashboard**
4. Click **Source** tab
5. Paste the XML above
6. Click **Save**

---

## Dashboard 2: Connection Monitoring

Monitor connection usage and detect connection leaks.

### Dashboard XML

```xml
<dashboard version="1.1" theme="light">
  <label>MariaDB Connection Monitoring</label>
  <description>Track connection usage and capacity</description>
  <row>
    <panel>
      <title>Active Connections Over Time</title>
      <chart>
        <search>
          <query>index=main sourcetype=metrics 
    (metric_name="mariadb.mariadb_global_status_threads_connected" OR
     metric_name="mariadb.mariadb_global_status_max_used_connections" OR
     metric_name="mariadb.mariadb_global_variables_max_connections")
| timechart span=1m avg(_value) by metric_name</query>
          <earliest>-60m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="charting.chart">line</option>
        <option name="charting.axisTitleX.text">Time</option>
        <option name="charting.axisTitleY.text">Connections</option>
        <option name="charting.legend.placement">bottom</option>
      </chart>
    </panel>
  </row>
</dashboard>
```

---

## Dashboard 3: Query Performance

Analyze query throughput and identify slow queries.

### Dashboard XML

```xml
<dashboard version="1.1" theme="light">
  <label>MariaDB Query Performance</label>
  <description>Monitor query throughput and slow queries</description>
  <row>
    <panel>
      <title>Query Throughput</title>
      <chart>
        <search>
          <query>index=main sourcetype=metrics 
    (metric_name="mariadb.mariadb_global_status_queries" OR
     metric_name="mariadb.mariadb_global_status_slow_queries")
| timechart span=1m rate(_value) as rate by metric_name
| eval Queries_per_sec=round('mariadb.mariadb_global_status_queries',2)
| eval Slow_Queries_per_sec=round('mariadb.mariadb_global_status_slow_queries',2)
| fields _time Queries_per_sec Slow_Queries_per_sec</query>
          <earliest>-60m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="charting.chart">line</option>
        <option name="charting.axisTitleX.text">Time</option>
        <option name="charting.axisTitleY.text">Queries/sec</option>
        <option name="charting.legend.placement">bottom</option>
      </chart>
    </panel>
  </row>
</dashboard>
```

---

## Dashboard 4: Resource Utilization

Track CPU, Memory, and Storage trends over time.

### Dashboard XML

```xml
<dashboard version="1.1" theme="light">
  <label>MariaDB Resource Utilization</label>
  <description>CPU, Memory, and Storage trends</description>
  <row>
    <panel>
      <title>CPU Usage</title>
      <chart>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_server_cpu"
| timechart span=1m avg(_value) as "CPU %" by server_name</query>
          <earliest>-60m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="charting.chart">area</option>
        <option name="charting.axisTitleY.text">CPU %</option>
      </chart>
    </panel>
    <panel>
      <title>Memory Usage (GB)</title>
      <chart>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_server_memory_rss"
| eval memory_gb=_value/1024/1024/1024
| timechart span=1m avg(memory_gb) as "Memory (GB)" by server_name</query>
          <earliest>-60m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="charting.chart">area</option>
        <option name="charting.axisTitleY.text">Memory (GB)</option>
      </chart>
    </panel>
  </row>
</dashboard>
```

---

## Dashboard 5: Complete Monitoring Dashboard

A comprehensive dashboard combining all key metrics.

### Dashboard XML

```xml
<dashboard version="1.1" theme="light">
  <label>MariaDB Cloud Complete Monitoring</label>
  <description>Comprehensive MariaDB Cloud metrics monitoring</description>
  <row>
    <panel>
      <title>Current Connections</title>
      <single>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_global_status_threads_connected"
| stats latest(_value) as connections</query>
          <earliest>-5m@m</earliest>
          <latest>now</latest>
          <refresh>30s</refresh>
        </search>
        <option name="drilldown">none</option>
        <option name="rangeColors">["0x53a051","0x0877a6","0xf8be34","0xf1813f","0xdc4e41"]</option>
        <option name="underLabel">Active Connections</option>
      </single>
    </panel>
    <panel>
      <title>CPU Usage</title>
      <single>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_server_cpu"
| stats avg(_value) as cpu
| eval cpu=round(cpu,1)</query>
          <earliest>-5m@m</earliest>
          <latest>now</latest>
          <refresh>30s</refresh>
        </search>
        <option name="drilldown">none</option>
        <option name="rangeColors">["0x53a051","0x0877a6","0xf8be34","0xf1813f","0xdc4e41"]</option>
        <option name="underLabel">CPU %</option>
      </single>
    </panel>
    <panel>
      <title>Queries/sec</title>
      <single>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_global_status_queries"
| timechart span=1m rate(_value) as qps
| stats latest(qps) as qps
| eval qps=round(qps,1)</query>
          <earliest>-5m@m</earliest>
          <latest>now</latest>
          <refresh>30s</refresh>
        </search>
        <option name="drilldown">none</option>
        <option name="underLabel">Queries per Second</option>
      </single>
    </panel>
  </row>
  <row>
    <panel>
      <title>CPU Usage Trend</title>
      <chart>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_server_cpu"
| timechart span=1m avg(_value) as "CPU %" by server_name</query>
          <earliest>-60m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="charting.chart">line</option>
        <option name="charting.axisTitleY.text">CPU %</option>
      </chart>
    </panel>
    <panel>
      <title>Active Connections Trend</title>
      <chart>
        <search>
          <query>index=main sourcetype=metrics metric_name="mariadb.mariadb_global_status_threads_connected"
| timechart span=1m avg(_value) as "Connections" by server_name</query>
          <earliest>-60m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="charting.chart">area</option>
        <option name="charting.axisTitleY.text">Connections</option>
      </chart>
    </panel>
  </row>
  <row>
    <panel>
      <title>Database Health Overview</title>
      <table>
        <search>
          <query>index=main sourcetype=metrics 
    (metric_name="mariadb.mariadb_server_cpu" OR 
     metric_name="mariadb.mariadb_server_memory_rss" OR 
     metric_name="mariadb.mariadb_global_status_threads_connected" OR
     metric_name="mariadb.mariadb_global_status_uptime")
| stats latest(_value) as value by metric_name, server_name
| eval metric_display=case(
    metric_name="mariadb.mariadb_server_cpu", "CPU %",
    metric_name="mariadb.mariadb_server_memory_rss", "Memory (bytes)",
    metric_name="mariadb.mariadb_global_status_threads_connected", "Active Connections",
    metric_name="mariadb.mariadb_global_status_uptime", "Uptime (seconds)"
)
| chart values(value) over server_name by metric_display</query>
          <earliest>-5m@m</earliest>
          <latest>now</latest>
          <refresh>1m</refresh>
        </search>
        <option name="drilldown">none</option>
      </table>
    </panel>
  </row>
</dashboard>
```

---

## Usage Instructions

### Import a Dashboard

1. Copy the XML for the dashboard you want
2. In Splunk Cloud, go to **Settings** → **User Interface** → **Dashboards**
3. Click **Create New Dashboard**
4. Switch to **Source** tab
5. Paste the XML
6. Click **Save**

### Customize Dashboards

- **Time Range:** Modify `<earliest>` and `<latest>` tags
- **Refresh Rate:** Modify `<refresh>` tag (e.g., `30s`, `1m`, `5m`)
- **Colors:** Modify `rangeColors` option
- **Chart Types:** Change `charting.chart` option (line, area, column, bar)

### Available Metrics

See `metrics-list.md` for the complete list of 89 available metrics.

### Best Practices

1. **Auto-refresh:** Set to 1-5 minutes for production dashboards
2. **Time ranges:** Use relative times (`-60m@m`, `-24h@h`) for consistency
3. **Permissions:** Share dashboards with your team via **Edit** → **Edit Permissions**
4. **Alerts:** Create alerts from dashboard searches via **Save As** → **Alert**

## Support

For more information:
- See `metrics/README.md` for integration documentation
- See `metrics/TEST_CHECKLIST.md` for verification steps
- MariaDB Cloud API: https://apidocs.skysql.com/
