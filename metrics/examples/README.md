# Deployment Examples for MariaDB Cloud Metrics Integration

This directory contains example configuration files for deploying the MariaDB Cloud metrics integration using different methods.

## Available Examples

### 1. Cron Job (`cron-example.sh`)

Traditional Unix cron job for scheduled execution.

**Usage:**
```bash
# Make executable
chmod +x cron-example.sh

# Edit with your credentials
vi cron-example.sh

# Add to crontab
crontab -e
# Add: */1 * * * * /path/to/cron-example.sh >> /var/log/mariadb_metrics.log 2>&1
```

**Best for:** Simple deployments, testing, development environments

---

### 2. macOS launchd (`launchd-example.plist`)

macOS service manager for automated execution.

**Usage:**
```bash
# Copy to LaunchAgents
cp launchd-example.plist ~/Library/LaunchAgents/com.mariadb.metrics.plist

# Edit with your credentials
vi ~/Library/LaunchAgents/com.mariadb.metrics.plist

# Load the service
launchctl load ~/Library/LaunchAgents/com.mariadb.metrics.plist

# Verify
launchctl list | grep mariadb
```

**Best for:** macOS production deployments, developer workstations

---

### 3. Linux systemd (`systemd-example.service` + `systemd-example.timer`)

Linux systemd service and timer for scheduled execution.

**Usage:**
```bash
# Copy files to systemd directory
sudo cp systemd-example.service /etc/systemd/system/mariadb-metrics.service
sudo cp systemd-example.timer /etc/systemd/system/mariadb-metrics.timer

# Edit with your credentials
sudo vi /etc/systemd/system/mariadb-metrics.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timer
sudo systemctl enable mariadb-metrics.timer
sudo systemctl start mariadb-metrics.timer

# Check status
sudo systemctl status mariadb-metrics.timer
sudo systemctl list-timers
```

**Best for:** Linux production deployments, enterprise environments

---

### 4. Kubernetes CronJob (`kubernetes-cronjob-example.yaml`)

Kubernetes CronJob for container-based deployments.

**Usage:**
```bash
# Edit with your credentials
vi kubernetes-cronjob-example.yaml

# Create ConfigMap from Python script
kubectl create configmap mariadb-metrics-script \
  --from-file=mariadb_metrics_input.py=../../scripts/mariadb_metrics_input.py \
  -n mariadb-monitoring

# Apply manifest
kubectl apply -f kubernetes-cronjob-example.yaml

# Verify
kubectl get cronjob -n mariadb-monitoring
kubectl get jobs -n mariadb-monitoring
```

**Best for:** Kubernetes environments, cloud-native deployments, microservices

---

## Configuration Placeholders

All example files use placeholder values that **must be replaced** with your actual credentials:

| Placeholder | Replace With | Where to Get It |
|-------------|--------------|-----------------|
| `your-mariadb-api-key` | Your actual MariaDB Cloud API key | MariaDB Cloud Portal → API Keys |
| `your-splunk-hec-token` | Your actual Splunk HEC token | Splunk Cloud → Settings → Data Inputs → HTTP Event Collector |
| `https://inputs.your-instance.splunkcloud.com:8088` | Your actual Splunk HEC URL | Splunk Cloud → Settings → Data Inputs → HTTP Event Collector |
| `/path/to/splunk-integration` | Actual installation path | Where you cloned this repository |

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
../../scripts/mariadb_metrics_wrapper.sh
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
