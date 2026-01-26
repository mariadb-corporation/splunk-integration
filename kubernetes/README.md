# Kubernetes Deployment for MariaDB Cloud Metrics Integration

This directory contains Kubernetes manifests for deploying the MariaDB Cloud metrics collector as a CronJob.

## Prerequisites

- Kubernetes cluster (tested with minikube)
- `kubectl` configured to access your cluster
- MariaDB Cloud API key
- Splunk Cloud HEC token

## Architecture

```
Kubernetes CronJob (every 1 minute)
  ↓
Pod with Python 3.11 container
  ↓
Install requests library
  ↓
Run mariadb_metrics_input.py
  ↓
Send metrics to Splunk Cloud HEC
```

## Files

- `mariadb-metrics-cronjob.yaml` - Main CronJob manifest with Namespace, Secret, ConfigMap, and CronJob
- `deploy.sh` - Deployment script that creates ConfigMap from Python script
- `README.md` - This file

## Deployment Steps

### 1. Create ConfigMap from Python Script

```bash
# Create ConfigMap containing the Python script
kubectl create configmap mariadb-metrics-script \
  --from-file=mariadb_metrics_input.py=../metrics/scripts/mariadb_metrics_input.py \
  --namespace=mariadb-monitoring \
  --dry-run=client -o yaml | kubectl apply -f -
```

Or use the deployment script:

```bash
./deploy.sh
```

### 2. Update Secrets (if needed)

Edit `mariadb-metrics-cronjob.yaml` and update:
- `MARIADB_API_KEY` - Your MariaDB Cloud API key
- `SPLUNK_HEC_TOKEN` - Your Splunk HEC token

### 3. Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f mariadb-metrics-cronjob.yaml

# Verify deployment
kubectl get all -n mariadb-monitoring
```

### 4. Verify CronJob

```bash
# Check CronJob status
kubectl get cronjob -n mariadb-monitoring

# Check recent jobs
kubectl get jobs -n mariadb-monitoring

# Check pods
kubectl get pods -n mariadb-monitoring
```

### 5. View Logs

```bash
# Get the most recent pod
POD=$(kubectl get pods -n mariadb-monitoring --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')

# View logs
kubectl logs -n mariadb-monitoring $POD

# Follow logs
kubectl logs -n mariadb-monitoring $POD -f
```

## Configuration

### Schedule

The CronJob runs every 1 minute by default. To change:

```yaml
spec:
  schedule: "*/5 * * * *"  # Every 5 minutes
```

### Environment Variables

All configuration is managed through ConfigMap and Secret:

**Secret (sensitive):**
- `MARIADB_API_KEY`
- `SPLUNK_HEC_TOKEN`

**ConfigMap (non-sensitive):**
- `MARIADB_API_URL`
- `SPLUNK_HEC_URL`
- `SPLUNK_HEC_VERIFY_SSL`
- `SPLUNK_INDEX`
- `SPLUNK_SOURCE`
- `SPLUNK_SOURCETYPE`
- `METRICS_CHECKPOINT_FILE`
- `METRICS_BATCH_SIZE`
- `METRICS_MAX_RETRIES`
- `METRICS_RETRY_DELAY`

### Resource Limits

Default resource limits:

```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "100m"
  limits:
    memory: "128Mi"
    cpu: "200m"
```

## Troubleshooting

### Check CronJob Status

```bash
kubectl describe cronjob mariadb-metrics-collector -n mariadb-monitoring
```

### Check Failed Jobs

```bash
kubectl get jobs -n mariadb-monitoring --field-selector status.successful=0
```

### View Pod Logs

```bash
# List all pods
kubectl get pods -n mariadb-monitoring

# View specific pod logs
kubectl logs <pod-name> -n mariadb-monitoring

# View previous pod logs (if crashed)
kubectl logs <pod-name> -n mariadb-monitoring --previous
```

### Common Issues

#### 1. ConfigMap Not Found

**Error:** `Error: configmaps "mariadb-metrics-script" not found`

**Solution:**
```bash
kubectl create namespace mariadb-monitoring
kubectl create configmap mariadb-metrics-script \
  --from-file=mariadb_metrics_input.py=../metrics/scripts/mariadb_metrics_input.py \
  -n mariadb-monitoring
kubectl apply -f mariadb-metrics-cronjob.yaml
```

#### 2. Secret Not Found

**Error:** `Error: secrets "mariadb-metrics-secrets" not found`

**Solution:** Ensure you've applied the `mariadb-metrics-cronjob.yaml` file

#### 3. Image Pull Errors

**Error:** `ImagePullBackOff`

**Solution:** Check internet connectivity or use a different Python image

#### 4. Permission Denied

**Error:** `Permission denied` on checkpoint file

**Solution:** The script automatically falls back to `/tmp` - this is expected

## Monitoring

### Check Metrics in Splunk

```spl
index=main sourcetype=metrics source=mariadbl_metrics_api
| stats count by metric_name
```

### Monitor CronJob Execution

```bash
# Watch jobs
kubectl get jobs -n mariadb-monitoring -w

# Check job history
kubectl get cronjob mariadb-metrics-collector -n mariadb-monitoring -o yaml | grep -A 5 status
```

## Cleanup

```bash
# Delete all resources
kubectl delete namespace mariadb-monitoring

# Or delete specific resources
kubectl delete cronjob mariadb-metrics-collector -n mariadb-monitoring
kubectl delete configmap mariadb-metrics-config mariadb-metrics-script -n mariadb-monitoring
kubectl delete secret mariadb-metrics-secrets -n mariadb-monitoring
```

## Production Recommendations

1. **Use Secrets Management:**
   - Use Kubernetes Secrets with encryption at rest
   - Consider using external secret managers (Vault, AWS Secrets Manager, etc.)

2. **Resource Limits:**
   - Adjust based on actual usage
   - Monitor pod resource consumption

3. **Monitoring:**
   - Set up alerts for failed jobs
   - Monitor pod restarts
   - Track metrics delivery to Splunk

4. **High Availability:**
   - Deploy to multiple nodes
   - Use pod disruption budgets
   - Consider using StatefulSet for checkpoint persistence

5. **Security:**
   - Enable SSL verification (`SPLUNK_HEC_VERIFY_SSL=true`)
   - Use network policies to restrict egress
   - Run as non-root user
   - Use read-only root filesystem

## Advanced Configuration

### Using Persistent Volume for Checkpoint

```yaml
volumes:
- name: checkpoint
  persistentVolumeClaim:
    claimName: metrics-checkpoint-pvc
```

### Using Init Container for Dependencies

```yaml
initContainers:
- name: install-deps
  image: python:3.11-slim
  command: ['pip', 'install', '--target=/deps', 'requests']
  volumeMounts:
  - name: deps
    mountPath: /deps
```

### Using Custom Python Image

Build a custom image with dependencies pre-installed:

```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir requests
COPY mariadb_metrics_input.py /app/
WORKDIR /app
CMD ["python3", "mariadb_metrics_input.py"]
```

## Support

For issues or questions:
- See main documentation: `../metrics/README.md`
- Check test results: `../DEPLOYMENT_TEST_RESULTS.md`
- MariaDB Cloud API: https://apidocs.skysql.com/
