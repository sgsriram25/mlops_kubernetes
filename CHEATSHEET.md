# Kubernetes Commands Cheat Sheet

## 🚀 Quick Reference for This Project

### Deploy Everything
```bash
kubectl apply -f k8s/
```

### Check Status
```bash
kubectl get all -n url-shortener
```

### Get External IP
```bash
kubectl get svc url-shortener-service -n url-shortener
```

### View Logs
```bash
kubectl logs -n url-shortener -l app.kubernetes.io/name=url-shortener -f
```

### Delete Everything
```bash
kubectl delete namespace url-shortener
```

---

## 📋 Essential kubectl Commands

### Cluster Info
| Command | Description |
|---------|-------------|
| `kubectl cluster-info` | Display cluster endpoint info |
| `kubectl get nodes` | List all nodes |
| `kubectl get nodes -o wide` | Nodes with extra details |
| `kubectl top nodes` | Node resource usage |

### Namespaces
| Command | Description |
|---------|-------------|
| `kubectl get namespaces` | List all namespaces |
| `kubectl create namespace <name>` | Create namespace |
| `kubectl delete namespace <name>` | Delete namespace (and all resources!) |

### Pods
| Command | Description |
|---------|-------------|
| `kubectl get pods -n <ns>` | List pods in namespace |
| `kubectl get pods -o wide` | Pods with node info |
| `kubectl describe pod <name> -n <ns>` | Detailed pod info |
| `kubectl logs <pod> -n <ns>` | View pod logs |
| `kubectl logs <pod> -n <ns> -f` | Stream logs |
| `kubectl logs <pod> -n <ns> --previous` | Previous container logs |
| `kubectl exec -it <pod> -n <ns> -- /bin/sh` | Shell into pod |
| `kubectl delete pod <name> -n <ns>` | Delete pod |

### Deployments
| Command | Description |
|---------|-------------|
| `kubectl get deployments -n <ns>` | List deployments |
| `kubectl describe deployment <name> -n <ns>` | Deployment details |
| `kubectl scale deployment <name> --replicas=<n> -n <ns>` | Scale deployment |
| `kubectl rollout status deployment/<name> -n <ns>` | Rollout status |
| `kubectl rollout history deployment/<name> -n <ns>` | Rollout history |
| `kubectl rollout undo deployment/<name> -n <ns>` | Rollback |
| `kubectl set image deployment/<name> <container>=<image> -n <ns>` | Update image |

### Services
| Command | Description |
|---------|-------------|
| `kubectl get services -n <ns>` | List services |
| `kubectl describe service <name> -n <ns>` | Service details |
| `kubectl get endpoints -n <ns>` | List endpoints |

### ConfigMaps & Secrets
| Command | Description |
|---------|-------------|
| `kubectl get configmaps -n <ns>` | List ConfigMaps |
| `kubectl describe configmap <name> -n <ns>` | ConfigMap details |
| `kubectl get secrets -n <ns>` | List secrets |
| `kubectl create secret generic <name> --from-literal=key=value` | Create secret |

### Autoscaling
| Command | Description |
|---------|-------------|
| `kubectl get hpa -n <ns>` | List HPAs |
| `kubectl describe hpa <name> -n <ns>` | HPA details |
| `kubectl top pods -n <ns>` | Pod resource usage |

### Events & Debugging
| Command | Description |
|---------|-------------|
| `kubectl get events -n <ns>` | List events |
| `kubectl get events --sort-by='.lastTimestamp' -n <ns>` | Events by time |
| `kubectl describe <resource> <name> -n <ns>` | Resource details |

### Apply & Delete
| Command | Description |
|---------|-------------|
| `kubectl apply -f <file.yaml>` | Apply manifest |
| `kubectl apply -f <directory>/` | Apply all in directory |
| `kubectl delete -f <file.yaml>` | Delete from manifest |
| `kubectl delete <resource> <name> -n <ns>` | Delete resource |

### Output Formats
| Flag | Description |
|------|-------------|
| `-o wide` | Extra columns |
| `-o yaml` | YAML output |
| `-o json` | JSON output |
| `-o jsonpath='{...}'` | Extract specific field |

---

## 🔧 Useful Aliases

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgs='kubectl get services'
alias kgd='kubectl get deployments'
alias kga='kubectl get all'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias ke='kubectl exec -it'
alias ka='kubectl apply -f'
alias kdel='kubectl delete'

# Namespace shortcut
alias kn='kubectl config set-context --current --namespace'
```

Usage:
```bash
kn url-shortener  # Set default namespace
kgp               # Get pods (in current namespace)
kl <pod> -f       # Stream logs
```

---

## 📊 Resource Units

### CPU
| Value | Meaning |
|-------|---------|
| `1` | 1 vCPU core |
| `500m` | 0.5 cores (500 millicores) |
| `100m` | 0.1 cores |

### Memory
| Value | Meaning |
|-------|---------|
| `128Mi` | 128 Mebibytes |
| `1Gi` | 1 Gibibyte |
| `256M` | 256 Megabytes |
