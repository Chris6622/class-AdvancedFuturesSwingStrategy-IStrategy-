# Freqtrade Cloud Deployment Guide

Complete guide to deploying your Freqtrade Futures Swing Strategy to the cloud.

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Deployment Options](#deployment-options)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Backup & Recovery](#backup--recovery)
8. [Security](#security)
9. [Troubleshooting](#troubleshooting)

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer / Ingress                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴───────────────┐
        │                              │
┌───────▼──────┐              ┌────────▼────────┐
│   Freqtrade  │              │    Grafana      │
│   Bot Pod    │              │   Dashboard     │
└───────┬──────┘              └────────┬────────┘
        │                              │
    ┌───┴────┬─────────────────────────┴───┐
    │        │                             │
┌───▼───┐ ┌──▼──────┐         ┌───────────▼───┐
│ Redis │ │ RDS/SQL │         │  Prometheus   │
│ Cache │ │Database │         │   Metrics     │
└───────┘ └─────────┘         └───────────────┘
```

## 📦 Prerequisites

### Required Tools

```bash
# Docker & Kubernetes
docker --version          # >= 20.10
kubectl version --client  # >= 1.25
helm version             # >= 3.10

# Cloud CLIs
aws --version            # For AWS
gcloud version           # For GCP
az version               # For Azure

# IaC Tools
terraform --version      # >= 1.5
```

### Install Tools (Ubuntu/Debian)

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

# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

## 🚀 Quick Start

### Option 1: Automated Deployment

```bash
# Clone repository
git clone <your-repo>
cd ft_userdata

# Configure secrets
cp .env.example .env
nano .env  # Edit with your values

# Deploy to AWS
chmod +x scripts/deploy.sh
./scripts/deploy.sh aws production deploy

# Or deploy to GCP
./scripts/deploy.sh gcp production deploy

# Or deploy to Azure
./scripts/deploy.sh azure production deploy
```

### Option 2: Step-by-Step Deployment

#### Step 1: Build Docker Image

```bash
docker build -t freqtrade:latest .
docker tag freqtrade:latest <your-registry>/freqtrade:latest
docker push <your-registry>/freqtrade:latest
```

#### Step 2: Deploy Infrastructure (Terraform)

```bash
cd terraform/aws  # or gcp/azure

# Initialize Terraform
terraform init

# Create workspace
terraform workspace new production

# Plan deployment
terraform plan -out=tfplan

# Apply
terraform apply tfplan
```

#### Step 3: Deploy to Kubernetes

```bash
# Update kubeconfig
aws eks update-kubeconfig --name freqtrade-cluster --region us-east-1

# Create namespace
kubectl create namespace freqtrade

# Create secrets
kubectl create secret generic freqtrade-secrets \
  --from-literal=postgres-password='<YOUR_PASSWORD>' \
  --from-literal=exchange-api-key='<YOUR_API_KEY>' \
  --from-literal=exchange-api-secret='<YOUR_SECRET>' \
  --from-literal=telegram-bot-token='<YOUR_TOKEN>' \
  --from-literal=telegram-chat-id='<YOUR_CHAT_ID>' \
  -n freqtrade

# Deploy
kubectl apply -f kubernetes/deployment.yaml

# Check status
kubectl get pods -n freqtrade
kubectl logs -f deployment/freqtrade -n freqtrade
```

## ☁️ Deployment Options

### AWS Deployment

**Resources Created:**
- EKS Cluster (Kubernetes)
- RDS PostgreSQL (Database)
- ElastiCache Redis (Caching)
- EFS (Persistent Storage)
- S3 (Backups)
- VPC, Subnets, Security Groups
- Load Balancer

**Cost Estimate:** ~$300-500/month

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_REGION="us-east-1"

# Deploy
cd terraform/aws
terraform init
terraform apply
```

### GCP Deployment

**Resources Created:**
- GKE Cluster
- Cloud SQL PostgreSQL
- Memorystore Redis
- Cloud Storage (Backups)
- VPC Network

**Cost Estimate:** ~$250-450/month

```bash
# Authenticate
gcloud auth login
gcloud config set project <PROJECT_ID>

# Deploy
cd terraform/gcp
terraform init
terraform apply
```

### Azure Deployment

**Resources Created:**
- AKS Cluster
- Azure Database for PostgreSQL
- Azure Cache for Redis
- Azure Storage Account
- Virtual Network

**Cost Estimate:** ~$300-500/month

```bash
# Login to Azure
az login

# Deploy
cd terraform/azure
terraform init
terraform apply
```

## ⚙️ Configuration

### Environment Variables

Edit `.env` file:

```bash
# Exchange
EXCHANGE_NAME=binance
EXCHANGE_KEY=your_api_key
EXCHANGE_SECRET=your_api_secret

# Database
POSTGRES_PASSWORD=secure_password_123

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=123456789

# Trading
STAKE_CURRENCY=USDT
MAX_OPEN_TRADES=5
DRY_RUN=false  # Set true for paper trading
```

### Kubernetes Secrets

```bash
# Update secrets in Kubernetes
kubectl edit secret freqtrade-secrets -n freqtrade

# Or recreate
kubectl delete secret freqtrade-secrets -n freqtrade
kubectl create secret generic freqtrade-secrets \
  --from-env-file=.env \
  -n freqtrade
```

### Strategy Parameters

Edit `user_data/config.json` for trading parameters.

## 📊 Monitoring

### Access Dashboards

```bash
# Get Grafana URL
kubectl get svc grafana -n freqtrade

# Port forward for local access
kubectl port-forward svc/grafana 3000:3000 -n freqtrade
# Access: http://localhost:3000
# Default: admin/admin
```

### View Logs

```bash
# Freqtrade logs
kubectl logs -f deployment/freqtrade -n freqtrade

# All pods
kubectl logs -f -l app=freqtrade -n freqtrade

# Last 100 lines
kubectl logs deployment/freqtrade -n freqtrade --tail=100
```

### Metrics

```bash
# Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n freqtrade
# Access: http://localhost:9090
```

## 💾 Backup & Recovery

### Automated Backups

Backups run daily at 3 AM UTC (configured in cron).

```bash
# Manual backup
kubectl exec deployment/postgres -n freqtrade -- \
  pg_dump -U freqtrade freqtrade > backup-$(date +%Y%m%d).sql

# Backup to S3 (AWS)
kubectl exec deployment/postgres -n freqtrade -- \
  pg_dump -U freqtrade freqtrade | \
  gzip | \
  aws s3 cp - s3://freqtrade-backups/backup-$(date +%Y%m%d).sql.gz
```

### Restore from Backup

```bash
# Restore database
cat backup-20260208.sql | \
  kubectl exec -i deployment/postgres -n freqtrade -- \
  psql -U freqtrade freqtrade

# Or from S3
aws s3 cp s3://freqtrade-backups/backup-20260208.sql.gz - | \
  gunzip | \
  kubectl exec -i deployment/postgres -n freqtrade -- \
  psql -U freqtrade freqtrade
```

## 🔒 Security

### Best Practices

1. **Use Secrets Manager**
```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name freqtrade/api-keys \
  --secret-string file://secrets.json

# Reference in Kubernetes using External Secrets Operator
```

2. **Enable Network Policies**
```bash
kubectl apply -f kubernetes/network-policies.yaml
```

3. **Setup TLS/SSL**
```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer for Let's Encrypt
kubectl apply -f kubernetes/cert-issuer.yaml
```

4. **Enable Pod Security**
```bash
# Apply pod security standards
kubectl label namespace freqtrade \
  pod-security.kubernetes.io/enforce=restricted
```

### Firewall Rules

- Only expose necessary ports
- Use security groups/firewall rules
- Enable VPN for management access
- Use bastion host for SSH

## 🔧 Troubleshooting

### Common Issues

#### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n freqtrade

# Check events
kubectl get events -n freqtrade --sort-by='.lastTimestamp'

# Check resource limits
kubectl top pods -n freqtrade
```

#### Database Connection Issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql -h postgres -U freqtrade -d freqtrade

# Check service endpoints
kubectl get endpoints -n freqtrade
```

#### API Not Accessible

```bash
# Check ingress
kubectl get ingress -n freqtrade
kubectl describe ingress freqtrade-ingress -n freqtrade

# Check load balancer
kubectl get svc freqtrade -n freqtrade
```

#### Hyperopt Not Running

```bash
# Check cron job
kubectl get cronjobs -n freqtrade
kubectl describe cronjob hyperopt-quarterly -n freqtrade

# Manual trigger
kubectl create job --from=cronjob/hyperopt-quarterly manual-hyperopt -n freqtrade
```

### Health Checks

```bash
# Check all resources
kubectl get all -n freqtrade

# Check node health
kubectl get nodes
kubectl top nodes

# Check cluster health
kubectl cluster-info
```

### Logs Analysis

```bash
# Search logs
kubectl logs deployment/freqtrade -n freqtrade | grep ERROR

# Export logs
kubectl logs deployment/freqtrade -n freqtrade > freqtrade.log

# Follow multiple pods
kubectl logs -f -l app=freqtrade -n freqtrade --all-containers
```

## 📞 Support

- **Freqtrade Docs**: https://www.freqtrade.io/
- **Kubernetes Docs**: https://kubernetes.io/docs/
- **Terraform Docs**: https://www.terraform.io/docs/

## 🔄 Updates & Maintenance

### Rolling Updates

```bash
# Update image
kubectl set image deployment/freqtrade \
  freqtrade=<new-image>:latest \
  -n freqtrade

# Check rollout status
kubectl rollout status deployment/freqtrade -n freqtrade

# Rollback if needed
kubectl rollout undo deployment/freqtrade -n freqtrade
```

### Scaling

```bash
# Scale horizontally
kubectl scale deployment/freqtrade --replicas=3 -n freqtrade

# Auto-scaling (HPA)
kubectl autoscale deployment/freqtrade \
  --min=1 --max=5 --cpu-percent=80 \
  -n freqtrade
```

---

**Ready to deploy!** 🚀 Start with the Quick Start section and customize as needed.

For production deployments, ensure all security measures are in place and start with paper trading (DRY_RUN=true) first.
