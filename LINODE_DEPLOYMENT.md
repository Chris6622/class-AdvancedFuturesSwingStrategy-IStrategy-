# Linode Deployment Guide for Freqtrade

Complete guide to deploying your Freqtrade Futures Swing Strategy on Linode.

## 🚀 Why Linode?

- **Cost-effective**: ~$180-240/month (vs AWS ~$300-500)
- **Simple pricing**: Predictable costs, no hidden fees
- **Fast deployment**: Managed Kubernetes (LKE) in minutes
- **Great performance**: AMD EPYC processors, NVMe SSD storage
- **Global reach**: 11 data centers worldwide
- **Excellent support**: 24/7 human support

## 💰 Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| LKE Nodes (2x) | g6-standard-2 (2 vCPU, 4GB) | $72 |
| LKE Node (1x) | g6-standard-4 (4 vCPU, 8GB) | $72 |
| Managed PostgreSQL | 1GB RAM | $15 |
| Block Storage | 70GB total | $7 |
| NodeBalancer | Load balancer | $10 |
| Object Storage | 250GB included | $5 |
| **Total** | | **~$180-240/month** |

**Includes**: 1TB bandwidth per Linode, DDoS protection, backups

## 📋 Prerequisites

### 1. Create Linode Account

1. Sign up at [linode.com](https://www.linode.com/)
2. Add payment method (new customers get $100 credit!)
3. Create API token:
   - Go to: https://cloud.linode.com/profile/tokens
   - Click "Create Personal Access Token"
   - Name: `freqtrade-deploy`
   - Permissions: Read/Write for all services
   - **Save the token securely**

### 2. Install Required Tools

**On Ubuntu/Debian:**
```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Terraform
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Linode CLI
pip3 install linode-cli
```

**On macOS:**
```bash
# Homebrew
brew install docker kubectl terraform linode-cli
```

**On Windows (PowerShell):**
```powershell
# Using Chocolatey
choco install docker-desktop kubernetes-cli terraform

# Linode CLI
pip install linode-cli
```

## 🎯 Quick Start (Automated)

### Option 1: One-Command Deployment

```bash
# Make script executable
chmod +x scripts/deploy-linode.sh

# Run deployment
./scripts/deploy-linode.sh
```

Follow the interactive menu to deploy!

### Option 2: Manual Step-by-Step

#### Step 1: Configure Terraform

```bash
cd terraform/linode

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

Update these values:
```hcl
linode_token   = "your_linode_api_token"
region         = "us-east"  # Choose your region
db_password    = "secure_password_123"
redis_password = "secure_redis_pass_123"
```

#### Step 2: Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Create workspace
terraform workspace new production

# Plan deployment
terraform plan -out=tfplan

# Apply (creates LKE cluster, database, storage, etc.)
terraform apply tfplan
```

This creates:
- ✅ Linode Kubernetes Engine (LKE) cluster
- ✅ Managed PostgreSQL database
- ✅ Block storage volumes
- ✅ NodeBalancer (load balancer)
- ✅ Object storage for backups
- ✅ Firewall rules

**Wait 5-10 minutes for cluster provisioning**

#### Step 3: Configure kubectl

```bash
# Get cluster ID
CLUSTER_ID=$(terraform output -raw cluster_id)

# Download kubeconfig
linode-cli lke kubeconfig-view $CLUSTER_ID --text | tail +2 | base64 -d > ~/.kube/linode-freqtrade
export KUBECONFIG=~/.kube/linode-freqtrade

# Verify connection
kubectl cluster-info
kubectl get nodes
```

#### Step 4: Build and Push Docker Image

```bash
cd ../..  # Back to project root

# Build image
docker build -t freqtrade:latest .

# Tag for registry (use Docker Hub, GitHub, etc.)
docker tag freqtrade:latest yourusername/freqtrade:latest

# Login to registry
docker login

# Push
docker push yourusername/freqtrade:latest
```

#### Step 5: Update Kubernetes Deployment

Edit `kubernetes/deployment.yaml`:
```yaml
# Change this line:
image: your-registry/freqtrade:latest
# To your actual image:
image: yourusername/freqtrade:latest
```

#### Step 6: Create Secrets

```bash
# Create namespace
kubectl create namespace freqtrade

# Get database info from Terraform
DB_HOST=$(cd terraform/linode && terraform output -raw database_host)
DB_PORT=$(cd terraform/linode && terraform output -raw database_port)

# Create secrets
kubectl create secret generic freqtrade-secrets \
  --from-literal=postgres-password='your_db_password' \
  --from-literal=exchange-api-key='your_binance_key' \
  --from-literal=exchange-api-secret='your_binance_secret' \
  --from-literal=telegram-bot-token='your_telegram_token' \
  --from-literal=telegram-chat-id='your_chat_id' \
  --from-literal=redis-password='your_redis_pass' \
  -n freqtrade
```

#### Step 7: Deploy Application

```bash
# Apply Kubernetes manifests
kubectl apply -f kubernetes/deployment.yaml

# Watch deployment
kubectl get pods -n freqtrade -w

# Check status
kubectl rollout status deployment/freqtrade -n freqtrade
```

#### Step 8: Verify Deployment

```bash
# Get LoadBalancer IP
kubectl get svc freqtrade -n freqtrade

# Test API (wait 30 seconds for service to start)
LB_IP=$(kubectl get svc freqtrade -n freqtrade -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://${LB_IP}:8080/api/v1/ping

# View logs
kubectl logs -f deployment/freqtrade -n freqtrade
```

## 🎛️ Advanced Configuration

### Custom Domain Setup

```bash
# Point your domain to the LoadBalancer IP
LB_IP=$(kubectl get svc freqtrade -n freqtrade -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Create DNS A record:
# freqtrade.yourdomain.com -> ${LB_IP}
```

### SSL/TLS with Cert-Manager

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Update ingress in kubernetes/deployment.yaml to use TLS
```

### Monitoring with Grafana

```bash
# Install Prometheus & Grafana
kubectl create namespace monitoring

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set prometheus.prometheusSpec.retention=30d

# Get Grafana password
kubectl get secret -n monitoring prometheus-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode

# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Open: http://localhost:3000
# Login: admin / <password from above>
```

## 📊 Monitoring & Management

### View Logs

```bash
# Live logs
kubectl logs -f deployment/freqtrade -n freqtrade

# Last 100 lines
kubectl logs deployment/freqtrade -n freqtrade --tail=100

# Search logs
kubectl logs deployment/freqtrade -n freqtrade | grep ERROR
```

### Shell Access

```bash
# Interactive shell
kubectl exec -it deployment/freqtrade -n freqtrade -- bash

# Run command
kubectl exec deployment/freqtrade -n freqtrade -- freqtrade show_config
```

### Resource Monitoring

```bash
# Pod resources
kubectl top pods -n freqtrade

# Node resources
kubectl top nodes

# Detailed pod info
kubectl describe pod <pod-name> -n freqtrade
```

### Database Management

```bash
# Connect to PostgreSQL
DB_HOST=$(cd terraform/linode && terraform output -raw database_host)
kubectl run -it --rm psql --image=postgres:15 --restart=Never -- \
  psql -h $DB_HOST -U freqtrade -d freqtrade

# Backup database
kubectl exec deployment/postgres -n freqtrade -- \
  pg_dump -U freqtrade freqtrade > backup-$(date +%Y%m%d).sql

# Restore database
cat backup.sql | kubectl exec -i deployment/postgres -n freqtrade -- \
  psql -U freqtrade freqtrade
```

## 🔄 Updates & Maintenance

### Rolling Update

```bash
# Build new image
docker build -t yourusername/freqtrade:v2 .
docker push yourusername/freqtrade:v2

# Update deployment
kubectl set image deployment/freqtrade \
  freqtrade=yourusername/freqtrade:v2 \
  -n freqtrade

# Watch rollout
kubectl rollout status deployment/freqtrade -n freqtrade

# Rollback if needed
kubectl rollout undo deployment/freqtrade -n freqtrade
```

### Scale Resources

```bash
# Scale pods
kubectl scale deployment/freqtrade --replicas=3 -n freqtrade

# Update resource limits (edit deployment)
kubectl edit deployment freqtrade -n freqtrade
```

### Backup Strategy

```bash
# Automated backups (already configured in cron)
# Manual backup
kubectl exec deployment/freqtrade -n freqtrade -- \
  /freqtrade/scripts/backup.sh

# List backups in Object Storage
linode-cli object-storage bucket ls freqtrade-cluster-backups
```

## 🛡️ Security Best Practices

### 1. Secure Secrets

```bash
# Use Sealed Secrets or External Secrets Operator
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system
```

### 2. Network Policies

```bash
# Apply network policies
kubectl apply -f kubernetes/network-policies.yaml
```

### 3. Regular Updates

```bash
# Update Kubernetes
linode-cli lke cluster-update <CLUSTER_ID> --k8s_version 1.29

# Update node pools
linode-cli lke pool-update <CLUSTER_ID> <POOL_ID>
```

### 4. Enable Audit Logging

Configure in Linode Cloud Manager:
- LKE → Your Cluster → Settings
- Enable audit logging
- Forward to your logging solution

## 💾 Backup & Recovery

### Automated Backups

Already configured via:
- Database: Automatic daily backups (7-day retention)
- Block Storage: Snapshots (manual or scheduled)
- Object Storage: Versioning enabled

### Manual Backup

```bash
# Full backup script
./scripts/backup.sh

# Backup to local
kubectl exec deployment/freqtrade -n freqtrade -- tar czf - /freqtrade/user_data | \
  cat > freqtrade-data-backup-$(date +%Y%m%d).tar.gz
```

### Disaster Recovery

```bash
# Restore from backup
cd terraform/linode
terraform apply  # Recreates infrastructure

# Restore database
cat backup.sql | kubectl exec -i deployment/postgres -n freqtrade -- \
  psql -U freqtrade freqtrade

# Redeploy application
kubectl apply -f kubernetes/deployment.yaml
```

## 💵 Cost Optimization

### 1. Use Smaller Nodes

```hcl
# In terraform/linode/main.tf
pool {
  type  = "g6-standard-1"  # 1 vCPU, 2GB RAM - $18/month
  count = 2
}
```

### 2. Single Database Node

```hcl
cluster_size = 1  # Instead of 3 (HA)
```

### 3. Reduce Storage

```hcl
size = 20  # Instead of 50GB
```

**Optimized cost**: ~$100-150/month

## 🆘 Troubleshooting

### Pods Not Starting

```bash
kubectl describe pod <pod-name> -n freqtrade
kubectl logs <pod-name> -n freqtrade
kubectl get events -n freqtrade --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Test connectivity
kubectl run -it --rm test-db --image=postgres:15 --restart=Never -- \
  psql -h <DB_HOST> -U freqtrade -d freqtrade

# Check credentials
kubectl get secret freqtrade-secrets -n freqtrade -o yaml
```

### LoadBalancer Not Getting IP

```bash
# Check NodeBalancer in Linode Cloud Manager
# Usually takes 2-3 minutes to provision

# Check service
kubectl describe svc freqtrade -n freqtrade
```

### Out of Resources

```bash
# Check node capacity
kubectl describe nodes

# Scale up node pool via Linode CLI
linode-cli lke pool-update <CLUSTER_ID> <POOL_ID> --count 3
```

## 📞 Support

- **Linode Support**: https://www.linode.com/support/
- **Community**: https://www.linode.com/community/
- **Documentation**: https://www.linode.com/docs/
- **Status**: https://status.linode.com/

## 🎉 Success!

Your Freqtrade bot is now running on Linode with:
- ✅ Managed Kubernetes cluster
- ✅ Highly available database
- ✅ Automatic backups
- ✅ Load balancing
- ✅ Monitoring ready
- ✅ Cost-optimized infrastructure

**Total setup time**: ~30 minutes  
**Monthly cost**: ~$180-240  
**Performance**: Excellent!

---

**Ready to trade!** 🚀 Remember to start with `DRY_RUN=true` for paper trading first.
