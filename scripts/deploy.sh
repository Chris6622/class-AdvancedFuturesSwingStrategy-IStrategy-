#!/bin/bash
# Cloud Deployment Script
# Supports AWS, GCP, Azure, and Linode

set -e

CLOUD_PROVIDER=${1:-aws}
ENVIRONMENT=${2:-production}
ACTION=${3:-deploy}

echo "=================================="
echo "Freqtrade Cloud Deployment"
echo "=================================="
echo "Provider: $CLOUD_PROVIDER"
echo "Environment: $ENVIRONMENT"
echo "Action: $ACTION"
echo "=================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_tools=()
    
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    command -v kubectl >/dev/null 2>&1 || missing_tools+=("kubectl")
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    
    if [ "$CLOUD_PROVIDER" == "aws" ]; then
        command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    elif [ "$CLOUD_PROVIDER" == "gcp" ]; then
        command -v gcloud >/dev/null 2>&1 || missing_tools+=("gcloud")
    elif [ "$CLOUD_PROVIDER" == "azure" ]; then
        command -v az >/dev/null 2>&1 || missing_tools+=("azure-cli")
    elif [ "$CLOUD_PROVIDER" == "linode" ]; then
        command -v linode-cli >/dev/null 2>&1 || missing_tools+=("linode-cli")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    log_info "All prerequisites met ✓"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."
    
    docker build -t freqtrade:latest .
    
    if [ $? -eq 0 ]; then
        log_info "Docker image built successfully ✓"
    else
        log_error "Docker build failed"
        exit 1
    fi
}

# Push to registry
push_image() {
    log_info "Pushing image to registry..."
    
    case $CLOUD_PROVIDER in
        aws)
            AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            AWS_REGION=${AWS_REGION:-us-east-1}
            ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/freqtrade"
            
            # Login to ECR
            aws ecr get-login-password --region ${AWS_REGION} | \
                docker login --username AWS --password-stdin ${ECR_REPO}
            
            # Tag and push
            docker tag freqtrade:latest ${ECR_REPO}:latest
            docker tag freqtrade:latest ${ECR_REPO}:${ENVIRONMENT}
            docker push ${ECR_REPO}:latest
            docker push ${ECR_REPO}:${ENVIRONMENT}
            ;;
        
        gcp)
            GCP_PROJECT=${GCP_PROJECT:-freqtrade-project}
            GCR_REPO="gcr.io/${GCP_PROJECT}/freqtrade"
            
            gcloud auth configure-docker
            docker tag freqtrade:latest ${GCR_REPO}:latest
            docker tag freqtrade:latest ${GCR_REPO}:${ENVIRONMENT}
            docker push ${GCR_REPO}:latest
            docker push ${GCR_REPO}:${ENVIRONMENT}
            ;;
        
        azure)
            ACR_NAME=${ACR_NAME:-freqtradeacr}
            az acr login --name ${ACR_NAME}
            docker tag freqtrade:latest ${ACR_NAME}.azurecr.io/freqtrade:latest
            docker tag freqtrade:latest ${ACR_NAME}.azurecr.io/freqtrade:${ENVIRONMENT}
            docker push ${ACR_NAME}.azurecr.io/freqtrade:latest
            docker push ${ACR_NAME}.azurecr.io/freqtrade:${ENVIRONMENT}
            ;;
        
        linode)
            # Use Docker Hub or GitHub Container Registry for Linode
            REGISTRY=${DOCKER_REGISTRY:-"docker.io"}
            REPO=${DOCKER_REPO:-"yourusername/freqtrade"}
            
            docker tag freqtrade:latest ${REGISTRY}/${REPO}:latest
            docker tag freqtrade:latest ${REGISTRY}/${REPO}:${ENVIRONMENT}
            docker push ${REGISTRY}/${REPO}:latest
            docker push ${REGISTRY}/${REPO}:${ENVIRONMENT}
            ;;
    esac
    
    log_info "Image pushed successfully ✓"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    log_info "Deploying infrastructure with Terraform..."
    
    cd terraform/${CLOUD_PROVIDER}
    
    terraform init
    terraform workspace select ${ENVIRONMENT} || terraform workspace new ${ENVIRONMENT}
    
    terraform plan -out=tfplan
    
    read -p "Apply Terraform plan? (yes/no): " confirm
    if [ "$confirm" == "yes" ]; then
        terraform apply tfplan
        log_info "Infrastructure deployed successfully ✓"
    else
        log_warn "Terraform apply cancelled"
        exit 0
    fi
    
    cd ../..
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    # Update kubeconfig
    case $CLOUD_PROVIDER in
        aws)
            CLUSTER_NAME=${CLUSTER_NAME:-freqtrade-cluster}
            aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION:-us-east-1}
            ;;
        gcp)
            CLUSTER_NAME=${CLUSTER_NAME:-freqtrade-cluster}
            GCP_ZONE=${GCP_ZONE:-us-central1-a}
            gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${GCP_ZONE}
            ;;
        azure)
            CLUSTER_NAME=${CLUSTER_NAME:-freqtrade-cluster}
            RESOURCE_GROUP=${RESOURCE_GROUP:-freqtrade-rg}
            az aks get-credentials --name ${CLUSTER_NAME} --resource-group ${RESOURCE_GROUP}
            ;;
        
        linode)
            CLUSTER_ID=$(cd terraform/linode && terraform output -raw cluster_id)
            linode-cli lke kubeconfig-view ${CLUSTER_ID} --text | tail +2 | base64 -d > ~/.kube/linode-freqtrade
            export KUBECONFIG=~/.kube/linode-freqtrade
            ;;
    esac
    
    # Apply Kubernetes manifests
    kubectl apply -f kubernetes/deployment.yaml
    
    # Wait for deployment
    log_info "Waiting for deployment to complete..."
    kubectl rollout status deployment/freqtrade -n freqtrade --timeout=10m
    
    log_info "Kubernetes deployment successful ✓"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check pod status
    kubectl get pods -n freqtrade
    
    # Check service health
    sleep 30
    ENDPOINT=$(kubectl get svc freqtrade -n freqtrade -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    
    if [ -n "$ENDPOINT" ]; then
        curl -f http://${ENDPOINT}:8080/api/v1/ping && \
            log_info "Health check passed ✓" || \
            log_error "Health check failed"
    else
        log_warn "LoadBalancer endpoint not ready yet"
    fi
}

# Main deployment flow
main() {
    check_prerequisites
    
    case $ACTION in
        deploy)
            build_image
            push_image
            deploy_infrastructure
            deploy_kubernetes
            verify_deployment
            log_info "Deployment complete! 🚀"
            ;;
        
        infrastructure)
            deploy_infrastructure
            ;;
        
        kubernetes)
            deploy_kubernetes
            verify_deployment
            ;;
        
        build)
            build_image
            push_image
            ;;
        
        destroy)
            log_warn "This will destroy all infrastructure!"
            read -p "Are you sure? Type 'yes' to confirm: " confirm
            if [ "$confirm" == "yes" ]; then
                cd terraform/${CLOUD_PROVIDER}
                terraform destroy
                cd ../..
                log_info "Infrastructure destroyed"
            fi
            ;;
        
        *)
            log_error "Unknown action: $ACTION"
            echo "Usage: $0 <aws|gcp|azure|linode> <environment> <deploy|infrastructure|kubernetes|build|destroy>"
            exit 1
            ;;
    esac
}

# Run main
main
