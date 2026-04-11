# URL Shortener on Google Kubernetes Engine (GKE)

A hands-on tutorial for deploying a FastAPI URL shortener service to GKE with production-ready Kubernetes configurations.

## 🎯 What You'll Learn

- Creating and configuring a GKE cluster
- Building and pushing Docker images to Google Container Registry (GCR)
- Writing production-grade Kubernetes manifests
- Implementing health checks (liveness/readiness probes)
- Configuring resource limits and requests
- Setting up Horizontal Pod Autoscaling (HPA)
- Using ConfigMaps for configuration management
- Ensuring high availability with PodDisruptionBudgets

## 📋 Prerequisites

- Google Cloud account with billing enabled
- Google Cloud SDK (`gcloud`) installed
- `kubectl` installed
- Docker installed
- Basic understanding of containers and APIs

## 🚀 Step-by-Step Deployment

### Step 1: Set Up Google Cloud Environment

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Set your preferred region
export REGION="us-central1"
export ZONE="us-central1-a"
```

### Step 2: Create a GKE Cluster

```bash
# Create a GKE cluster with autoscaling enabled
gcloud container clusters create url-shortener-cluster \
    --zone $ZONE \
    --num-nodes 2 \
    --min-nodes 1 \
    --max-nodes 4 \
    --enable-autoscaling \
    --machine-type e2-medium \
    --enable-ip-alias

# Get credentials to interact with the cluster
gcloud container clusters get-credentials url-shortener-cluster --zone $ZONE
```

### Step 3: Verify Cluster Connection

```bash
# Check cluster info
kubectl cluster-info

# List nodes
kubectl get nodes

# Expected output: 2 nodes in "Ready" status
```

### Step 4: Build and Push Docker Image

```bash
# Navigate to the app directory
cd app/

# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker

# Build the Docker image
docker build -t gcr.io/$PROJECT_ID/url-shortener:v1.0.0 .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/url-shortener:v1.0.0

# Verify the image exists
gcloud container images list --repository=gcr.io/$PROJECT_ID
```

### Step 5: Update Deployment Image Reference

Before deploying, update the image in `k8s/03-deployment.yaml`:

```yaml
# Change this line:
image: python:3.11-slim

# To your GCR image:
image: gcr.io/YOUR_PROJECT_ID/url-shortener:v1.0.0
```

And remove the `command` and `args` sections since your image already contains the app.

### Step 6: Deploy to Kubernetes

```bash
# Navigate to k8s directory
cd ../k8s/

# Apply all manifests in order
kubectl apply -f 01-namespace.yaml
kubectl apply -f 02-configmap.yaml
kubectl apply -f 03-deployment.yaml
kubectl apply -f 04-service.yaml
kubectl apply -f 05-hpa.yaml
kubectl apply -f 06-pdb.yaml

# Or apply all at once
kubectl apply -f .
```

### Step 7: Verify Deployment

```bash
# Check namespace was created
kubectl get namespaces | grep url-shortener

# Check all resources in the namespace
kubectl get all -n url-shortener

# Check deployment status
kubectl get deployment url-shortener -n url-shortener

# Check pods are running
kubectl get pods -n url-shortener -o wide

# Check service and external IP
kubectl get service url-shortener-service -n url-shortener

# Check HPA status
kubectl get hpa -n url-shortener
```

### Step 8: Wait for External IP

```bash
# Watch for external IP assignment (may take 1-2 minutes)
kubectl get service url-shortener-service -n url-shortener --watch

# Once you see an EXTERNAL-IP, press Ctrl+C
```

### Step 9: Test the Application

```bash
# Set the external IP
export EXTERNAL_IP=$(kubectl get service url-shortener-service -n url-shortener -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Test root endpoint
curl http://$EXTERNAL_IP/

# Test health endpoint
curl http://$EXTERNAL_IP/health

# Test readiness endpoint
curl http://$EXTERNAL_IP/ready

# Create a shortened URL
curl -X POST http://$EXTERNAL_IP/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://kubernetes.io/docs/home/"}'

# Visit the API documentation
echo "Open in browser: http://$EXTERNAL_IP/docs"
```

## 🔍 Monitoring and Debugging

### View Pod Logs

```bash
# Get logs from a specific pod
kubectl logs -n url-shortener <pod-name>

# Stream logs from all pods
kubectl logs -n url-shortener -l app.kubernetes.io/name=url-shortener -f

# Get logs from previous container instance (if crashed)
kubectl logs -n url-shortener <pod-name> --previous
```

### Describe Resources

```bash
# Detailed info about deployment
kubectl describe deployment url-shortener -n url-shortener

# Detailed info about a pod
kubectl describe pod <pod-name> -n url-shortener

# Check events in the namespace
kubectl get events -n url-shortener --sort-by='.lastTimestamp'
```

### Execute Commands in Pod

```bash
# Get a shell inside a pod
kubectl exec -it <pod-name> -n url-shortener -- /bin/sh

# Check environment variables
kubectl exec -it <pod-name> -n url-shortener -- env | grep APP
```

## 📊 Scaling Operations

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment url-shortener -n url-shortener --replicas=5

# Verify scaling
kubectl get pods -n url-shortener
```

### Automatic Scaling (HPA)

```bash
# Check HPA status
kubectl get hpa -n url-shortener

# Watch HPA in action
kubectl get hpa -n url-shortener --watch

# Generate load to trigger scaling (from another terminal)
# Install hey: go install github.com/rakyll/hey@latest
hey -n 10000 -c 100 http://$EXTERNAL_IP/health
```

## 🔄 Update and Rollback

### Rolling Update

```bash
# Update to a new image version
kubectl set image deployment/url-shortener \
  url-shortener=gcr.io/$PROJECT_ID/url-shortener:v1.1.0 \
  -n url-shortener

# Watch the rollout
kubectl rollout status deployment/url-shortener -n url-shortener

# Check rollout history
kubectl rollout history deployment/url-shortener -n url-shortener
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/url-shortener -n url-shortener

# Rollback to specific revision
kubectl rollout undo deployment/url-shortener -n url-shortener --to-revision=1
```

## 🧹 Cleanup

```bash
# Delete all resources in the namespace
kubectl delete namespace url-shortener

# Delete the GKE cluster
gcloud container clusters delete url-shortener-cluster --zone $ZONE

# Delete the container image
gcloud container images delete gcr.io/$PROJECT_ID/url-shortener:v1.0.0 --force-delete-tags
```

## 📚 Key Concepts Covered

| Concept | File | Purpose |
|---------|------|---------|
| Namespace | 01-namespace.yaml | Isolates resources |
| ConfigMap | 02-configmap.yaml | Stores configuration |
| Deployment | 03-deployment.yaml | Manages pods |
| Service | 04-service.yaml | Exposes pods |
| HPA | 05-hpa.yaml | Auto-scaling |
| PDB | 06-pdb.yaml | Availability |

## 🔧 Kubernetes Components Explained

### Resource Requests vs Limits

```yaml
resources:
  requests:     # Guaranteed resources for scheduling
    cpu: "100m"
    memory: "128Mi"
  limits:       # Maximum resources allowed
    cpu: "500m"
    memory: "256Mi"
```

### Probe Types

| Probe | Purpose | Failure Action |
|-------|---------|----------------|
| Liveness | Is container alive? | Restart container |
| Readiness | Is container ready? | Remove from service |

### Labels Best Practices

Use the `app.kubernetes.io/` prefix for standard labels:
- `app.kubernetes.io/name`: Application name
- `app.kubernetes.io/component`: Component within the app
- `app.kubernetes.io/version`: Application version

## 📖 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
