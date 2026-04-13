# URL Shortener on Google Kubernetes Engine (GKE)

Here we will containerize a FastAPI microservice and deploy it to Google Kubernetes Engine with full observability, autoscaling, and zero-downtime update patterns.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Application Deep Dive](#4-application-deep-dive)
5. [Prerequisites](#5-prerequisites)
6. [Part 1 — Run Locally (Without Docker)](#part-1--run-locally-without-docker)
7. [Part 2 — Build and Test with Docker](#part-2--build-and-test-with-docker)
8. [Part 3 — Google Cloud Setup](#part-3--google-cloud-setup)
9. [Part 4 — Create the GKE Cluster](#part-4--create-the-gke-cluster)
10. [Part 5 — Build and Push to Google Container Registry](#part-5--build-and-push-to-google-container-registry)
11. [Part 6 — Deploy to Kubernetes](#part-6--deploy-to-kubernetes)
12. [Part 7 — Verify the Deployment](#part-7--verify-the-deployment)
13. [Part 8 — Test the Live API](#part-8--test-the-live-api)
14. [Kubernetes Manifests Reference](#kubernetes-manifests-reference)
15. [Monitoring and Debugging](#monitoring-and-debugging)
16. [Scaling](#scaling)
17. [Rolling Updates and Rollbacks](#rolling-updates-and-rollbacks)
18. [Cleanup](#cleanup)
19. [Troubleshooting](#troubleshooting)
20. [Key Concepts Reference](#key-concepts-reference)

---

## 1. Project Overview

This project deploys a **URL Shortener** microservice to GKE using production-grade Kubernetes patterns. The service is intentionally simple so the focus stays on infrastructure — but every pattern here applies directly to real-world MLOps pipelines, model-serving APIs, and data services.



| Skill | Where It Appears |
|---|---|
| Multi-stage Docker builds | `app/Dockerfile` |
| Namespace isolation | `k8s/01-namespace.yaml` |
| Externalizing config from code | `k8s/02-configmap.yaml` |
| Zero-downtime rolling updates | `k8s/03-deployment.yaml` |
| Cloud load balancing | `k8s/04-service.yaml` |
| CPU/memory-based autoscaling | `k8s/05-hpa.yaml` |
| Protecting uptime during maintenance | `k8s/06-pdb.yaml` |
| Health probes (liveness + readiness) | `app/main.py`, `k8s/03-deployment.yaml` |

---

## 2. Architecture

```
                          Internet
                             │
                    ┌────────▼────────┐
                    │  GCP Cloud      │
                    │  Load Balancer  │  (created by Service type: LoadBalancer)
                    │  Port 80        │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │     GKE Cluster             │
              │     (us-central1-a)         │
              │                             │
              │  Namespace: url-shortener   │
              │                             │
              │  ┌─────────┐ ┌─────────┐   │
              │  │  Pod 1  │ │  Pod 2  │   │
              │  │ :8080   │ │ :8080   │   │  ← HPA scales 2–10 replicas
              │  └─────────┘ └─────────┘   │
              │  ┌─────────┐               │
              │  │  Pod 3  │               │
              │  │ :8080   │               │
              │  └─────────┘               │
              │                             │
              │  ConfigMap ──► all Pods     │
              │  PDB: min 1 available       │
              └─────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Google Container Registry  │
              │  gcr.io/$PROJECT_ID/        │
              │  url-shortener:v1.0.0       │
              └─────────────────────────────┘
```

**Request flow:**
1. Client sends HTTP request to the external IP on port 80
2. GCP Cloud Load Balancer forwards it to one of the healthy pods on port 8080
3. FastAPI handles the request; config values come from the ConfigMap
4. Kubernetes continuously checks `/health` (liveness) and `/ready` (readiness) to route traffic only to healthy pods

---

## 3. Repository Structure

```
MLOps_kubernetes/
│
├── app/                        # Application source code
│   ├── main.py                 # FastAPI application (all endpoints)
│   ├── requirements.txt        # Pinned Python dependencies
│   ├── Dockerfile              # Multi-stage production Docker image
│   └── .dockerignore           # Files excluded from Docker build context
│
├── k8s/                        # Kubernetes manifests (apply in numeric order)
│   ├── 01-namespace.yaml       # Isolated namespace for all resources
│   ├── 02-configmap.yaml       # Non-sensitive runtime configuration
│   ├── 03-deployment.yaml      # Pod template, replicas, probes, resource limits
│   ├── 04-service.yaml         # LoadBalancer exposing pods externally
│   ├── 05-hpa.yaml             # HorizontalPodAutoscaler (CPU + memory metrics)
│   └── 06-pdb.yaml             # PodDisruptionBudget for maintenance safety
│
├── CHEATSHEET.md               # Quick kubectl reference
└── README.md                   # This file
```

---

## 4. Application Deep Dive

The application is a stateless FastAPI service (`app/main.py`) that shortens URLs using an MD5 hash. Configuration is injected at runtime from Kubernetes ConfigMap environment variables.

### API Endpoints

| Method | Path | Purpose | Kubernetes Use |
|---|---|---|---|
| `GET` | `/` | API info and links | — |
| `GET` | `/health` | Liveness probe | Restart pod if unhealthy |
| `GET` | `/ready` | Readiness probe | Remove from LB if not ready |
| `POST` | `/shorten` | Create short URL | Core business logic |
| `GET` | `/r/{short_code}` | Redirect to original URL | Core business logic |
| `GET` | `/stats/{short_code}` | Visit count + metadata | Observability |
| `GET` | `/urls` | List all URLs | Debug/demo |
| `GET` | `/docs` | Swagger UI (auto-generated) | Development |

### Environment Variables (from ConfigMap)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `url-shortener` | Appears in health responses |
| `ENVIRONMENT` | `development` | `production` in ConfigMap |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `BASE_URL` | `http://localhost:8080` | Used to build short URLs; update after LB IP is assigned |

### Dependencies

```
fastapi==0.109.0    # Web framework
uvicorn==0.27.0     # ASGI server
pydantic==2.5.3     # Request/response validation
```

### Docker Image (Multi-Stage Build)

The Dockerfile uses a two-stage build to minimize the final image size and attack surface:

- **Stage 1 (builder):** installs dependencies into an isolated virtual environment (`/opt/venv`)
- **Stage 2 (production):** copies only the venv and `main.py`; creates a non-root user (`appuser:appgroup`); runs on port 8080

```
Builder stage  →  python:3.11-slim + venv + pip install
Production stage →  python:3.11-slim + /opt/venv (copied) + main.py
                    HEALTHCHECK every 30s against /health
                    USER appuser (non-root)
                    CMD uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 5. Prerequisites

Install and verify each tool before starting.

### Required Tools

| Tool | Minimum Version | Install |
|---|---|---|
| Google Cloud SDK (`gcloud`) | 400+ | https://cloud.google.com/sdk/docs/install |
| `kubectl` | 1.27+ | `gcloud components install kubectl` |
| Docker Desktop | 24+ | https://docs.docker.com/get-docker/ |
| Python | 3.11+ | https://python.org (for local dev only) |

### Verify Installations

```bash
gcloud version
kubectl version --client
docker --version
python --version
```

### Google Cloud Requirements

- A Google Cloud project with **billing enabled**
- Your account must have the following IAM roles (or Owner):
  - `roles/container.admin` — manage GKE clusters
  - `roles/storage.admin` — push images to GCR
  - `roles/iam.serviceAccountUser` — use service accounts

---

## Part 1 — Run Locally (Without Docker)

Verify the application works before containerizing it.

```bash
# Clone/navigate to the repo
cd app/

# Create a virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Open your browser at http://localhost:8080/docs to see the Swagger UI. Test a few endpoints:

```bash
# Health check
curl http://localhost:8080/health

# Shorten a URL
curl -X POST http://localhost:8080/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://kubernetes.io/docs/home/"}'

# Expected response:
# {
#   "original_url": "https://kubernetes.io/docs/home/",
#   "short_code": "3faa6b0a",
#   "short_url": "http://localhost:8080/r/3faa6b0a",
#   "created_at": "2024-01-15T10:30:00.123456"
# }
```

Stop the server (`Ctrl+C`) and deactivate the venv before proceeding.

---

## Part 2 — Build and Test with Docker

### 2.1 Build the Image

```bash
cd app/

# Build the image and tag it
docker build -t url-shortener:v1.0.0 .

# Verify the image was created
docker images url-shortener
```

### 2.2 Run the Container Locally

```bash
docker run -d \
  --name url-shortener-test \
  -p 8080:8080 \
  -e APP_NAME="url-shortener" \
  -e ENVIRONMENT="development" \
  -e BASE_URL="http://localhost:8080" \
  url-shortener:v1.0.0
```

### 2.3 Test the Container

```bash
# Check container is running
docker ps --filter name=url-shortener-test

# Test the health endpoint
curl http://localhost:8080/health

# Check Docker's built-in health status
docker inspect url-shortener-test --format='{{.State.Health.Status}}'
# Should show: healthy (after ~30 seconds)
```

### 2.4 Inspect Logs and Clean Up

```bash
# View logs
docker logs url-shortener-test

# Stream logs
docker logs -f url-shortener-test

# Stop and remove the test container
docker stop url-shortener-test
docker rm url-shortener-test
```

---

## Part 3 — Google Cloud Setup

### 3.1 Authenticate and Set Project

```bash
# Log in to Google Cloud
gcloud auth login

# Set your project ID (replace with your actual project ID)
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Confirm the active project
gcloud config get-value project
```

### 3.2 Set Region and Zone

```bash
export REGION="us-central1"
export ZONE="us-central1-a"

gcloud config set compute/region $REGION
gcloud config set compute/zone $ZONE
```

### 3.3 Enable Required APIs

```bash
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled | grep -E "container|registry"
```

### 3.4 Configure Docker to Use gcloud Credentials

```bash
gcloud auth configure-docker
```

This adds `gcr.io` as a Docker credential helper so `docker push` can authenticate automatically.

---

## Part 4 — Create the GKE Cluster

### 4.1 Create the Cluster

```bash
gcloud container clusters create url-shortener-cluster \
  --zone $ZONE \
  --num-nodes 2 \
  --min-nodes 1 \
  --max-nodes 4 \
  --enable-autoscaling \
  --machine-type e2-medium \
  --enable-ip-alias \
  --no-enable-basic-auth \
  --metadata disable-legacy-endpoints=true
```

**Flag explanations:**

| Flag | Value | Why |
|---|---|---|
| `--num-nodes` | 2 | Initial node count |
| `--min-nodes` / `--max-nodes` | 1–4 | Node-level autoscaling |
| `--machine-type` | e2-medium | 2 vCPU, 4 GB RAM per node |
| `--enable-ip-alias` | — | Required for VPC-native networking |
| `--no-enable-basic-auth` | — | Security hardening |

Cluster creation takes approximately **3–5 minutes**.

### 4.2 Fetch Cluster Credentials

This command writes a `kubeconfig` entry so `kubectl` points to your new cluster.

```bash
gcloud container clusters get-credentials url-shortener-cluster --zone $ZONE
```

### 4.3 Verify the Connection

```bash
# Show cluster endpoint and version
kubectl cluster-info

# List nodes and their status
kubectl get nodes -o wide
```

Expected output — both nodes should show `Ready`:

```
NAME                                STATUS   ROLES    AGE   VERSION
gke-url-shortener-cluster-...       Ready    <none>   2m    v1.28.x
gke-url-shortener-cluster-...       Ready    <none>   2m    v1.28.x
```

---

## Part 5 — Build and Push to Google Container Registry

### 5.1 Tag the Image for GCR

```bash
docker tag url-shortener:v1.0.0 gcr.io/$PROJECT_ID/url-shortener:v1.0.0
```

### 5.2 Push the Image

```bash
docker push gcr.io/$PROJECT_ID/url-shortener:v1.0.0
```

### 5.3 Verify the Image Exists in GCR

```bash
gcloud container images list --repository=gcr.io/$PROJECT_ID

gcloud container images describe gcr.io/$PROJECT_ID/url-shortener:v1.0.0
```

### 5.4 Update the Deployment Manifest

Open `k8s/03-deployment.yaml` and replace the demo image reference with your GCR image. Find the `containers` section and make the following changes:

**Before:**
```yaml
image: python:3.11-slim
command: ["/bin/sh", "-c"]
args:
  - |
    pip install fastapi uvicorn pydantic --quiet && ...
```

**After:**
```yaml
image: gcr.io/YOUR_PROJECT_ID/url-shortener:v1.0.0
```

Remove the entire `command` and `args` fields — your image already contains the app and the correct `CMD`.

```bash
# Quick sed replacement (substitute your actual project ID):
sed -i "s|image: python:3.11-slim|image: gcr.io/$PROJECT_ID/url-shortener:v1.0.0|" k8s/03-deployment.yaml

# Manually remove the command/args block, then verify
grep -A 3 "image:" k8s/03-deployment.yaml
```

---

## Part 6 — Deploy to Kubernetes

Apply the manifests in numerical order. Each file depends on the previous one (the namespace must exist before any resource is placed in it).

### 6.1 Apply Manifests One by One

```bash
cd k8s/

# 1. Create the namespace
kubectl apply -f 01-namespace.yaml

# 2. Create the ConfigMap (app configuration)
kubectl apply -f 02-configmap.yaml

# 3. Create the Deployment (pods + rolling update strategy)
kubectl apply -f 03-deployment.yaml

# 4. Create the Service (cloud load balancer)
kubectl apply -f 04-service.yaml

# 5. Create the HPA (autoscaling policy)
kubectl apply -f 05-hpa.yaml

# 6. Create the PDB (disruption budget)
kubectl apply -f 06-pdb.yaml
```

### 6.2 Alternative: Apply All at Once

```bash
kubectl apply -f k8s/
```

> Note: `kubectl apply -f .` processes files in alphabetical order. The numeric prefixes ensure correct ordering.

---

## Part 7 — Verify the Deployment

### 7.1 Check All Resources in the Namespace

```bash
kubectl get all -n url-shortener
```

Expected output (pods may still be `ContainerCreating` initially):

```
NAME                                READY   STATUS    RESTARTS   AGE
pod/url-shortener-xxxxxxxxx-xxxxx   1/1     Running   0          90s
pod/url-shortener-xxxxxxxxx-xxxxx   1/1     Running   0          90s
pod/url-shortener-xxxxxxxxx-xxxxx   1/1     Running   0          90s

NAME                            TYPE           CLUSTER-IP     EXTERNAL-IP    PORT(S)        AGE
service/url-shortener-service   LoadBalancer   10.96.xxx.xxx  <pending>      80:31xxx/TCP   90s

NAME                        READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/url-shortener   3/3     3            3           90s

NAME                                                REFERENCE              TARGETS   MINPODS   MAXPODS   REPLICAS
horizontalpodautoscaler.apps/url-shortener-hpa      Deployment/url-shortener   2%/70%    2         10        3
```

### 7.2 Check Each Resource Type

```bash
# Deployment status
kubectl get deployment url-shortener -n url-shortener

# Pod status with node assignment
kubectl get pods -n url-shortener -o wide

# Service and external IP
kubectl get service url-shortener-service -n url-shortener

# HPA current metrics
kubectl get hpa -n url-shortener

# PDB status
kubectl get pdb -n url-shortener
```

### 7.3 Wait for the External IP

The LoadBalancer IP can take 1–3 minutes to be provisioned by GCP.

```bash
# Watch until EXTERNAL-IP appears (Ctrl+C to stop)
kubectl get service url-shortener-service -n url-shortener --watch
```

Once provisioned, capture the IP:

```bash
export EXTERNAL_IP=$(kubectl get service url-shortener-service \
  -n url-shortener \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "External IP: $EXTERNAL_IP"
```

### 7.4 Update the BASE_URL in ConfigMap

Now that you have the real IP, update the ConfigMap so shortened URLs include the correct base:

```bash
kubectl patch configmap url-shortener-config \
  -n url-shortener \
  --type merge \
  -p "{\"data\":{\"BASE_URL\":\"http://$EXTERNAL_IP\"}}"

# Restart pods to pick up the new config
kubectl rollout restart deployment/url-shortener -n url-shortener

# Wait for rollout to complete
kubectl rollout status deployment/url-shortener -n url-shortener
```

---

## Part 8 — Test the Live API

### 8.1 Basic Connectivity

```bash
# Root endpoint
curl http://$EXTERNAL_IP/

# Liveness check
curl http://$EXTERNAL_IP/health

# Readiness check
curl http://$EXTERNAL_IP/ready
```

### 8.2 Shorten a URL

```bash
curl -X POST http://$EXTERNAL_IP/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://kubernetes.io/docs/home/"}'
```

Sample response:

```json
{
  "original_url": "https://kubernetes.io/docs/home/",
  "short_code": "3faa6b0a",
  "short_url": "http://<EXTERNAL_IP>/r/3faa6b0a",
  "created_at": "2024-01-15T10:30:00.123456"
}
```

### 8.3 Follow the Redirect

```bash
# -L follows the redirect
curl -L http://$EXTERNAL_IP/r/3faa6b0a
```

### 8.4 Get Stats

```bash
curl http://$EXTERNAL_IP/stats/3faa6b0a
```

### 8.5 List All URLs

```bash
curl http://$EXTERNAL_IP/urls
```

### 8.6 Interactive API Documentation

Open in your browser:

```
http://<EXTERNAL_IP>/docs
```

The Swagger UI lets you explore and test all endpoints interactively.

---

## Kubernetes Manifests Reference

### 01-namespace.yaml — Namespace

Provides logical isolation for all project resources. Resources in different namespaces cannot reference each other without explicit configuration.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: url-shortener
  labels:
    app.kubernetes.io/name: url-shortener
    app.kubernetes.io/part-of: url-shortener-stack
    environment: production
```

All subsequent resources specify `namespace: url-shortener` to be placed here.

---

### 02-configmap.yaml — ConfigMap

Stores non-sensitive configuration as key-value pairs. Pods consume these as environment variables via `envFrom`. This separates config from the container image — the same image runs in dev and prod with different ConfigMaps.

```yaml
data:
  APP_NAME: "url-shortener"
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  BASE_URL: "http://localhost:8080"   # Update after LB IP is assigned
```

**Important:** ConfigMaps are not for secrets. Use Kubernetes Secrets (or External Secrets Operator) for API keys, passwords, and tokens.

---

### 03-deployment.yaml — Deployment

The most complex manifest. Key sections:

**Replicas and update strategy:**
```yaml
replicas: 3
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # Create 1 new pod before removing an old one
    maxUnavailable: 0  # Never go below desired replica count → zero downtime
```

**Pod anti-affinity** (spread pods across nodes — prevents a single node failure from taking down the entire service):
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: url-shortener
          topologyKey: kubernetes.io/hostname
```

**Resource requests vs limits:**
```yaml
resources:
  requests:
    cpu: "100m"      # Guaranteed scheduling allocation (0.1 core)
    memory: "128Mi"  # Guaranteed memory
  limits:
    cpu: "500m"      # Hard cap (0.5 core) — prevents noisy neighbor
    memory: "256Mi"  # OOMKill threshold
```

**Liveness probe** — if this fails 3 times, Kubernetes restarts the container:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 15   # Wait before first check
  periodSeconds: 20
  timeoutSeconds: 5
  failureThreshold: 3
```

**Readiness probe** — if this fails, the pod is removed from the Service's endpoint list (no traffic sent):
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

---

### 04-service.yaml — Service

Creates a stable network endpoint in front of the pods. `LoadBalancer` type automatically provisions a GCP Cloud Load Balancer with a public IP.

```yaml
spec:
  type: LoadBalancer
  selector:
    app.kubernetes.io/name: url-shortener
    app.kubernetes.io/component: api
  ports:
    - port: 80          # External-facing port
      targetPort: 8080  # Container port
```

The selector must match the pod labels in the Deployment's pod template.

---

### 05-hpa.yaml — HorizontalPodAutoscaler

Automatically adjusts the replica count based on real-time metrics. Requires the Metrics Server to be running in the cluster (GKE enables this by default).

```yaml
spec:
  minReplicas: 2    # Always keep at least 2 pods for HA
  maxReplicas: 10   # Cost ceiling
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70   # Scale out if avg CPU > 70%
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80   # Scale out if avg memory > 80%
```

**Scale-up behavior:** Immediate, max of (double current pods) or (add 4 pods), whichever is larger.

**Scale-down behavior:** 5-minute stabilization window, reduce by at most 50% per minute (prevents thrashing).

---

### 06-pdb.yaml — PodDisruptionBudget

Prevents cluster maintenance operations (node drains, upgrades) from taking down too many pods simultaneously.

```yaml
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: url-shortener
      app.kubernetes.io/component: api
```

With `minAvailable: 1`, Kubernetes will not drain a node if doing so would leave 0 pods available. It will wait until another pod comes up elsewhere first.

---

## Monitoring and Debugging

### View Logs

```bash
# Logs from a specific pod
kubectl logs <pod-name> -n url-shortener

# Stream logs from all pods with matching label
kubectl logs -n url-shortener \
  -l app.kubernetes.io/name=url-shortener \
  -f

# Logs from a crashed container's previous run
kubectl logs <pod-name> -n url-shortener --previous
```

### Describe Resources

`kubectl describe` shows events, conditions, and detailed state — essential for diagnosing `Pending` or `CrashLoopBackOff` pods.

```bash
# Deployment
kubectl describe deployment url-shortener -n url-shortener

# Specific pod
kubectl describe pod <pod-name> -n url-shortener

# Service (check endpoint assignments)
kubectl describe service url-shortener-service -n url-shortener

# HPA (see current metrics and scaling events)
kubectl describe hpa url-shortener-hpa -n url-shortener
```

### Namespace Events (Chronological)

```bash
kubectl get events -n url-shortener --sort-by='.lastTimestamp'
```

### Execute Commands Inside a Pod

```bash
# Open a shell
kubectl exec -it <pod-name> -n url-shortener -- /bin/sh

# Check environment variables from ConfigMap
kubectl exec -it <pod-name> -n url-shortener -- env | grep -E "APP_|ENV|BASE|LOG"

# Check the app is listening
kubectl exec -it <pod-name> -n url-shortener -- wget -qO- http://localhost:8080/health
```

### Port-Forward for Local Debugging

Access a pod directly without going through the load balancer:

```bash
kubectl port-forward pod/<pod-name> 9090:8080 -n url-shortener
# Now accessible at http://localhost:9090
```

---

## Scaling

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment url-shortener -n url-shortener --replicas=5

# Confirm
kubectl get pods -n url-shortener
```

Note: If the HPA is active, it will override a manual scale after the next reconciliation loop. Disable the HPA or set `minReplicas` to the desired count if you need a fixed replica count.

### Load Testing to Trigger HPA

Install `hey` (a HTTP load generator):

```bash
go install github.com/rakyll/hey@latest
```

Generate load:

```bash
# 10,000 requests, 100 concurrent
hey -n 10000 -c 100 http://$EXTERNAL_IP/health
```

Watch the HPA respond in real time:

```bash
kubectl get hpa -n url-shortener --watch
```

### Viewing Current HPA Metrics

```bash
kubectl top pods -n url-shortener    # Requires metrics-server
kubectl describe hpa url-shortener-hpa -n url-shortener
```

---

## Rolling Updates and Rollbacks

### Deploy a New Version

Build and push a new image version:

```bash
# In app/
docker build -t gcr.io/$PROJECT_ID/url-shortener:v1.1.0 .
docker push gcr.io/$PROJECT_ID/url-shortener:v1.1.0
```

Update the running deployment without editing YAML:

```bash
kubectl set image deployment/url-shortener \
  url-shortener=gcr.io/$PROJECT_ID/url-shortener:v1.1.0 \
  -n url-shortener
```

### Monitor the Rollout

```bash
# Block until rollout completes (or fails)
kubectl rollout status deployment/url-shortener -n url-shortener

# Watch pods cycling
kubectl get pods -n url-shortener --watch
```

Because `maxUnavailable: 0`, new pods come up and pass their readiness probe before old ones are terminated — zero downtime.

### View Rollout History

```bash
kubectl rollout history deployment/url-shortener -n url-shortener
```

### Rollback

```bash
# Roll back to the previous version
kubectl rollout undo deployment/url-shortener -n url-shortener

# Roll back to a specific revision number
kubectl rollout undo deployment/url-shortener -n url-shortener --to-revision=1

# Confirm rollback completed
kubectl rollout status deployment/url-shortener -n url-shortener
```

---

## Cleanup

Delete resources in reverse order to avoid dependency errors.

### Delete Kubernetes Resources Only

```bash
# Delete everything in the namespace (including the namespace itself)
kubectl delete namespace url-shortener
```

### Delete the GKE Cluster

```bash
gcloud container clusters delete url-shortener-cluster \
  --zone $ZONE \
  --quiet
```

### Delete the Container Image from GCR

```bash
gcloud container images delete \
  gcr.io/$PROJECT_ID/url-shortener:v1.0.0 \
  --force-delete-tags \
  --quiet

# If you pushed v1.1.0:
gcloud container images delete \
  gcr.io/$PROJECT_ID/url-shortener:v1.1.0 \
  --force-delete-tags \
  --quiet
```

### Delete All GCR Images for This Repo

```bash
gcloud container images list-tags gcr.io/$PROJECT_ID/url-shortener \
  --format='get(digest)' | \
  xargs -I {} gcloud container images delete \
    gcr.io/$PROJECT_ID/url-shortener@{} --force-delete-tags --quiet
```

---

## Troubleshooting

### Pods Stuck in `Pending`

```bash
kubectl describe pod <pod-name> -n url-shortener
```

Common causes:
- **Insufficient cluster resources:** scale up the node pool or reduce resource requests
- **Image pull failure:** verify `gcr.io/$PROJECT_ID/url-shortener:v1.0.0` exists and `gcloud auth configure-docker` was run
- **PodDisruptionBudget blocking eviction:** check `kubectl describe pdb -n url-shortener`

### Pods in `CrashLoopBackOff`

```bash
kubectl logs <pod-name> -n url-shortener --previous
```

Common causes:
- Application error on startup (check Python traceback in logs)
- Missing required environment variable
- Port conflict (verify `containerPort: 8080` matches what uvicorn binds)

### Service Shows `<pending>` for External IP

GCP Load Balancer provisioning takes 1–3 minutes. If it stays pending after 5 minutes:

```bash
kubectl describe service url-shortener-service -n url-shortener
# Look for "Error" in the Events section
```

Verify your project has billing enabled and the `container.googleapis.com` API is active.

### HPA Shows `<unknown>` for Metrics

The HPA needs the Kubernetes Metrics Server. On GKE it should already be running:

```bash
kubectl get deployment metrics-server -n kube-system
```

If missing, install it:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### ConfigMap Changes Not Reflected in Pods

Pods load environment variables at startup; they do not automatically pick up ConfigMap updates. After patching a ConfigMap:

```bash
kubectl rollout restart deployment/url-shortener -n url-shortener
```

---

## Key Concepts Reference

### Kubernetes Object Hierarchy

```
Cluster
└── Namespace
    ├── Deployment  →  manages →  ReplicaSet  →  manages →  Pods
    ├── Service     →  routes traffic to Pods (via label selector)
    ├── ConfigMap   →  injected into Pods as env vars or volume files
    ├── HPA         →  adjusts Deployment replica count
    └── PDB         →  limits simultaneous pod disruptions
```

### Probe Comparison

| | Liveness | Readiness |
|---|---|---|
| **Endpoint** | `/health` | `/ready` |
| **Failure action** | Restart the container | Remove pod from Service endpoints |
| **Use for** | Detecting deadlocks, hangs | Detecting startup lag, downstream outages |
| **Initial delay** | 15 seconds | 5 seconds |

### Resource Units

| Unit | Meaning |
|---|---|
| `100m` CPU | 100 millicores = 0.1 vCPU |
| `500m` CPU | 500 millicores = 0.5 vCPU |
| `128Mi` memory | 128 mebibytes ≈ 134 MB |
| `256Mi` memory | 256 mebibytes ≈ 268 MB |

### Label Conventions

This project uses the [recommended Kubernetes labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/):

| Label | Value | Purpose |
|---|---|---|
| `app.kubernetes.io/name` | `url-shortener` | Application name |
| `app.kubernetes.io/component` | `api`, `config`, `service`, etc. | Role within the app |
| `app.kubernetes.io/version` | `1.0.0` | Image/app version |
| `app.kubernetes.io/part-of` | `url-shortener-stack` | Higher-level grouping |

---

## Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Kubernetes HPA Walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/)
- [GKE Best Practices](https://cloud.google.com/kubernetes-engine/docs/best-practices)
