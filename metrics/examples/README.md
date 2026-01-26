# MariaDB Cloud Metrics - Deployment Examples

This directory contains ready-to-use deployment examples for the MariaDB Cloud metrics integration.

## 🚀 Recommended: Daemon Mode

**Daemon mode is the recommended approach** for continuous metrics collection. The collector runs as a persistent process and polls metrics at regular intervals, which is more efficient than cron-based execution.

### Benefits of Daemon Mode:
- ✅ Single persistent process (no repeated startup overhead)
- ✅ Configurable polling interval
- ✅ Graceful shutdown handling
- ✅ Automatic restart on failure (with systemd/launchd)
- ✅ Better resource utilization
- ✅ Easier monitoring and logging

## Available Examples

### 1. Daemon Mode (`daemon-example.sh`) ⭐ RECOMMENDED

Runs the collector as a continuous daemon process.

**Usage:**
```bash
# Make executable
chmod +x daemon-example.sh

# Edit with your credentials
vi daemon-example.sh

# Run daemon with 60 second interval
./daemon-example.sh

# Or run directly with custom interval
python3 ../scripts/mariadb_metrics_input.py --daemon --interval 60
```

**Best for:** Production deployments, continuous monitoring, all environments

**CLI Options:**
- `--daemon`: Enable daemon mode (continuous polling)
- `--interval N`: Set polling interval in seconds (default: 60)

---

### 2. macOS launchd (`launchd-example.plist`) ⭐

macOS service manager running in daemon mode.

**Usage:**
```bash
# Edit with your credentials and paths
vi launchd-example.plist

# Copy to LaunchAgents
cp launchd-example.plist ~/Library/LaunchAgents/com.mariadb.metrics.plist

# Load the service
launchctl load ~/Library/LaunchAgents/com.mariadb.metrics.plist

# Check status
launchctl list | grep mariadb

# View logs
tail -f /var/log/mariadb_metrics.log

# Stop service
launchctl unload ~/Library/LaunchAgents/com.mariadb.metrics.plist
```

**Configuration:** Uses daemon mode with 60 second interval, automatic restart on failure

**Best for:** macOS servers, development machines, developer workstations

---

### 3. Linux systemd (`systemd-example.service`) ⭐

Systemd service running in daemon mode with automatic restart.

**Usage:**
```bash
# Edit with your credentials
vi systemd-example.service

# Copy to systemd directory
sudo cp systemd-example.service /etc/systemd/system/mariadb-metrics.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable mariadb-metrics.service
sudo systemctl start mariadb-metrics.service

# Check status
sudo systemctl status mariadb-metrics.service

# View logs
sudo journalctl -u mariadb-metrics.service -f

# Stop service
sudo systemctl stop mariadb-metrics.service
```

**Configuration:** Uses daemon mode with 60 second interval, automatic restart on failure

**Best for:** Linux servers, production environments, enterprise environments

---

### 4. Kubernetes Deployment (`kubernetes-deployment-example.yaml`) ⭐

Kubernetes Deployment running in daemon mode with automatic restart.

**Usage:**
```bash
# Edit with your credentials
vi kubernetes-deployment-example.yaml

# Create ConfigMap from Python script
kubectl create configmap mariadb-metrics-script \
  --from-file=mariadb_metrics_input.py=../scripts/mariadb_metrics_input.py \
  -n mariadb-monitoring

# Apply manifest
kubectl apply -f kubernetes-deployment-example.yaml

# Verify
kubectl get deployment -n mariadb-monitoring
kubectl get pods -n mariadb-monitoring
kubectl logs -f deployment/mariadb-metrics-collector -n mariadb-monitoring
```

**Configuration:** Uses daemon mode with configurable interval via ConfigMap

**Best for:** Kubernetes clusters, containerized environments, cloud-native deployments

---

### 5. Cron Job (`cron-example.sh`) - Legacy

Traditional cron-based scheduling (kept for backward compatibility).

**Note:** Daemon mode is recommended over cron for production use.

**Usage:**
```bash
# Make executable
chmod +x cron-example.sh

# Edit with your credentials
vi cron-example.sh

# Add to crontab
crontab -e
# Add: */1 * * * * /path/to/metrics/examples/cron-example.sh >> /var/log/mariadb_metrics.log 2>&1
```

**Best for:** Simple deployments, testing, backward compatibility

**Note:** Kubernetes CronJob example is also available as `kubernetes-cronjob-example.yaml` for legacy deployments.

---

## Configuration Placeholders

All example files use placeholder values that **must be replaced** with your actual credentials:

| Placeholder | Replace With | Where to Get It |
|-------------|--------------|-----------------|
| `your-mariadb-api-key` | Your actual MariaDB Cloud API key | MariaDB Cloud Portal → API Keys |
| `your-splunk-hec-token` | Your actual Splunk HEC token | Splunk Cloud → Settings → Data Inputs → HTTP Event Collector |
| `https://inputs.your-instance.splunkcloud.com:8088` | Your actual Splunk HEC URL | Splunk Cloud → Settings → Data Inputs → HTTP Event Collector |
| `/path/to/splunk-integration` | Actual installation path | Where you cloned this repository (metrics scripts are in metrics/scripts/) |
| `60` (interval) | Polling interval in seconds | How often to collect metrics (default: 60 seconds, recommended: 60-300) |

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** or secrets management systems
3. **Enable SSL verification** (`SPLUNK_HEC_VERIFY_SSL=true`) in production
4. **Restrict file permissions** on configuration files:
   ```bash
   chmod 600 launchd-example.plist
   chmod 600 systemd-example.service
   ```
5. **Use Kubernetes Secrets** for container deployments
6. **Rotate credentials** regularly

## Testing Your Configuration

Before deploying, test your configuration:

```bash
# Set environment variables
export MARIADB_API_KEY="your-mariadb-api-key"
export MARIADB_API_URL="https://api.skysql.com"
export SPLUNK_HEC_TOKEN="your-splunk-hec-token"
export SPLUNK_HEC_URL="https://inputs.your-instance.splunkcloud.com:8088"
export SPLUNK_HEC_VERIFY_SSL="true"

# Run manually
../scripts/mariadb_metrics_wrapper.sh
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify API key is correct
   - Check API key has not expired
   - Ensure API key has read access to Observability API

2. **HEC Connection Failed**
   - Verify HEC token is correct
   - Check HEC is enabled in Splunk Cloud
   - Verify network connectivity to Splunk Cloud

3. **Permission Denied**
   - Check file permissions
   - Ensure user has execute permissions
   - Verify checkpoint directory is writable

## Additional Resources

- Main Documentation: `../README.md`
- Test Checklist: `../TEST_CHECKLIST.md`
- Splunk Dashboards: `../SPLUNK_DASHBOARDS.md`
- Kubernetes Guide: `../../kubernetes/README.md`
- Deployment Test Results: `../../DEPLOYMENT_TEST_RESULTS.md`

## Support

For issues or questions:
- MariaDB Cloud API: https://apidocs.skysql.com/
- MariaDB Cloud Documentation: https://docs.skysql.com/Observability/
