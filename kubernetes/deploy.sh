#!/bin/bash
#
# Kubernetes Deployment Script for MariaDB Cloud Metrics Integration
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="mariadb-monitoring"

echo "=== MariaDB Cloud Metrics - Kubernetes Deployment ==="
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster"
    echo "Please ensure your cluster is running and kubectl is configured"
    exit 1
fi

echo "✓ kubectl is available"
echo "✓ Kubernetes cluster is accessible"
echo ""

# Create namespace
echo "Creating namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Create ConfigMap from Python script
echo "Creating ConfigMap with Python script..."
kubectl create configmap mariadb-metrics-script \
  --from-file=mariadb_metrics_input.py=$SCRIPT_DIR/../metrics/scripts/mariadb_metrics_input.py \
  --namespace=$NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✓ ConfigMap created"
echo ""

# Apply CronJob manifest
echo "Deploying CronJob and related resources..."
kubectl apply -f $SCRIPT_DIR/mariadb-metrics-cronjob.yaml

echo "✓ CronJob deployed"
echo ""

# Wait a moment for resources to be created
sleep 2

# Show deployment status
echo "=== Deployment Status ==="
echo ""
echo "Namespace:"
kubectl get namespace $NAMESPACE
echo ""
echo "ConfigMaps:"
kubectl get configmap -n $NAMESPACE
echo ""
echo "Secrets:"
kubectl get secret -n $NAMESPACE
echo ""
echo "CronJobs:"
kubectl get cronjob -n $NAMESPACE
echo ""

echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Wait for the CronJob to run (every 1 minute)"
echo "2. Check job status: kubectl get jobs -n $NAMESPACE"
echo "3. View logs: kubectl logs -n $NAMESPACE <pod-name>"
echo "4. Monitor in Splunk: index=main sourcetype=metrics source=mariadbl_metrics_api"
echo ""
echo "To view logs from the most recent pod:"
echo "  POD=\$(kubectl get pods -n $NAMESPACE --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')"
echo "  kubectl logs -n $NAMESPACE \$POD -f"
echo ""
