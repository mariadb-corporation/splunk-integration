# MariaDB Cloud Logs - Deployment Examples

This directory contains ready-to-use deployment examples for the MariaDB Cloud logs
integration. All methods run the collector as a persistent process that polls
the MariaDB Cloud Logs API and sends log lines to Splunk Cloud via the HTTP Event
Collector (HEC) — no Splunk Universal Forwarder is required.

## 🚀 Recommended: Daemon Mode

**Daemon mode is the recommended approach** for continuous log collection. The
collector runs as a persistent process and polls at regular intervals.

### Benefits of Daemon Mode:
- ✅ Single persistent process (no repeated startup overhead)
- ✅ Configurable polling interval
- ✅ Graceful shutdown handling (SIGTERM/SIGINT)
- ✅ Automatic restart on failure (with systemd/launchd)

## Available Examples

### 1. Daemon Mode (`daemon-example.sh`) ⭐ RECOMMENDED

```bash
chmod +x daemon-example.sh
vi daemon-example.sh                 # edit with your credentials
./daemon-example.sh

# Or run directly with a custom interval
python3 ../scripts/mariadb_logs_collector.py --daemon --interval 300
```

**CLI Options:**
- `--daemon`: Enable daemon mode (continuous polling)
- `--interval N`: Polling interval in seconds (default: 300)
- `--verbose`: Enable DEBUG logging (e.g. per-archive dedup skip counts)

**Best for:** Continuous monitoring, all environments

---

### 2. macOS launchd (`launchd-example.plist`) ⭐

```bash
vi launchd-example.plist             # edit with your credentials and paths
cp launchd-example.plist ~/Library/LaunchAgents/com.mariadb.logs.plist
launchctl load ~/Library/LaunchAgents/com.mariadb.logs.plist
launchctl list | grep mariadb
tail -f /var/log/mariadb_logs.log
launchctl unload ~/Library/LaunchAgents/com.mariadb.logs.plist   # stop
```

**Best for:** macOS servers and developer workstations

---

### 3. Linux systemd (`systemd-example.service`) ⭐

```bash
vi systemd-example.service           # edit with your credentials
sudo cp systemd-example.service /etc/systemd/system/mariadb-logs.service
sudo systemctl daemon-reload
sudo systemctl enable mariadb-logs.service
sudo systemctl start mariadb-logs.service
sudo systemctl status mariadb-logs.service
sudo journalctl -u mariadb-logs.service -f
```

**Best for:** Linux servers, enterprise environments

---

### 4. Kubernetes Deployment (`kubernetes-deployment-example.yaml`) ⭐

```bash
vi kubernetes-deployment-example.yaml   # edit with your credentials

# Create ConfigMap from the Python script
kubectl create configmap mariadb-logs-script \
  --from-file=mariadb_logs_collector.py=../scripts/mariadb_logs_collector.py \
  -n mariadb-monitoring

kubectl apply -f kubernetes-deployment-example.yaml
kubectl get deployment -n mariadb-monitoring
kubectl logs -f deployment/mariadb-logs-collector -n mariadb-monitoring
```

**Note:** The manifest mounts a PersistentVolumeClaim for the dedup checkpoint
so restarts don't re-ingest already-sent logs. It uses `replicas: 1` with a
`Recreate` strategy so the checkpoint is never written by two pods at once.

**Best for:** Kubernetes clusters, cloud-native deployments

---

## Configuration Placeholders

All example files use placeholder values that **must be replaced** with your
actual credentials:

| Placeholder | Replace With | Where to Get It |
|-------------|--------------|-----------------|
| `your-mariadb-api-key` | Your MariaDB Cloud API key | MariaDB Cloud Portal → API Keys |
| `your-splunk-hec-token` | Your Splunk HEC token | Splunk Cloud → Settings → Data Inputs → HTTP Event Collector |
| `https://inputs.your-instance.splunkcloud.com:8088` | Your Splunk HEC URL | Splunk Cloud → Settings → Data Inputs → HTTP Event Collector |
| `/path/to/splunk-integration` | Actual installation path | Where you cloned this repository (logs scripts are in `logs/scripts/`) |
| `300` (interval) | Polling interval in seconds | How often to collect logs (default: 300) |

## The Checkpoint File

Unlike the metrics collector, the logs collector keeps a **checkpoint file**
(`CHECKPOINT_FILE`, default `./mariadb_checkpoint.json`) that records the
last-seen timestamp per log archive to avoid re-sending the same lines. Point
it at a durable location (e.g. `/var/lib/mariadb-logs/…` or a mounted volume) so
dedup state survives restarts.

## Testing Your Configuration

```bash
export MARIADB_API_KEY="your-mariadb-api-key"
export MARIADB_API_URL="https://api.skysql.com"
export SPLUNK_HEC_TOKEN="your-splunk-hec-token"
export SPLUNK_HEC_URL="https://inputs.your-instance.splunkcloud.com:8088"
export SPLUNK_HEC_VERIFY_SSL="true"

# Run once (no --daemon) to verify end-to-end delivery
../scripts/mariadb_logs_wrapper.sh
```

## Support

- MariaDB Cloud API Docs: https://apidocs.skysql.com/
- MariaDB Cloud Observability: https://docs.skysql.com/Observability/
- Splunk Docs: https://docs.splunk.com/
