#!/bin/bash
# Linode Deployment Script for Freqtrade

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    local missing=()
    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v kubectl >/dev/null 2>&1 || missing+=("kubectl")
    command -v terraform >/dev/null 2>&1 || missing+=("terraform")
    command -v linode-cli >/dev/null 2>&1 || missing+=("linode-cli")
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        log_info "Install them with:"
        echo "  - docker: https://docs.docker.com/get-docker/"
        echo "  - kubectl: https://kubernetes.io/docs/tasks/tools/"
        echo "  - terraform: https://www.terraform.io/downloads"
        echo "  - linode-cli: pip install linode-cli"
        exit 1
    fi
    
    log_info "All prerequisites met ✓"
}

# Setup Linode CLI
setup_linode_cli() {
    log_step "Setting up Linode CLI..."
    
    if [ -z "$LINODE_CLI_TOKEN" ]; then
        log_warn "LINODE_CLI_TOKEN not set"
        echo "Get your token from: https://cloud.linode.com/profile/tokens"
        read -p "Enter your Linode API token: " LINODE_CLI_TOKEN
        export LINODE_CLI_TOKEN
    fi
    
    # Configure linode-cli
    linode-cli configure --token
    
    log_info "Linode CLI configured ✓"
}

# Build Docker image
build_image() {
    log_step "Building Docker image..."
    
    cd "$PROJECT_ROOT"
    docker build -t freqtrade:latest -f Dockerfile .
    
    if [ $? -eq 0 ]; then
        log_info "Docker image built ✓"
    else
        log_error "Docker build failed"
        exit 1
    fi
}

# Push to Docker registry
push_image() {
    log_step "Pushing image to registry..."
    
    # You can use Docker Hub, GitHub Container Registry, or Linode Container Registry
    REGISTRY=${DOCKER_REGISTRY:-"docker.io"}
    REPO=${DOCKER_REPO:-"yourusername/freqtrade"}
    
    docker tag freqtrade:latest ${REGISTRY}/${REPO}:latest
    docker tag freqtrade:latest ${REGISTRY}/${REPO}:$(date +%Y%m%d-%H%M%S)
    
    docker push ${REGISTRY}/${REPO}:latest
    docker push ${REGISTRY}/${REPO}:$(date +%Y%m%d-%H%M%S)
    
    log_info "Image pushed ✓"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    log_step "Deploying Linode infrastructure..."
    
    cd "$PROJECT_ROOT/terraform/linode"
    
    # Check if terraform.tfvars exists
    if [ ! -f terraform.tfvars ]; then
        log_warn "terraform.tfvars not found"
        cp terraform.tfvars.example terraform.tfvars
        log_info "Created terraform.tfvars from example"
        log_warn "Please edit terraform.tfvars with your values"
        exit 1
    fi
    
    # Initialize Terraform
    terraform init
    
    # Select or create workspace
    terraform workspace select production || terraform workspace new production
    
    # Plan
    terraform plan -out=tfplan
    
    # Confirm
    read -p "Apply Terraform plan? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_warn "Terraform apply cancelled"
        exit 0
    fi
    
    # Apply
    terraform apply tfplan
    
    if [ $? -eq 0 ]; then
        log_info "Infrastructure deployed ✓"
        
        # Save outputs
        terraform output -json > outputs.json
        
        # Export kubeconfig
        terraform output -raw kubeconfig > kubeconfig.yaml
        export KUBECONFIG="$PWD/kubeconfig.yaml"
        
        log_info "Kubeconfig exported to: $PWD/kubeconfig.yaml"
    else
        log_error "Terraform apply failed"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
}

# Configure kubectl
configure_kubectl() {
    log_step "Configuring kubectl..."
    
    # Get cluster ID
    CLUSTER_ID=$(cd "$PROJECT_ROOT/terraform/linode" && terraform output -raw cluster_id)
    
    # Get kubeconfig
    linode-cli lke kubeconfig-view "$CLUSTER_ID" --text | tail +2 | base64 -d > ~/.kube/linode-freqtrade-config
    
    export KUBECONFIG=~/.kube/linode-freqtrade-config
    
    # Test connection
    kubectl cluster-info
    
    log_info "kubectl configured ✓"
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_step "Deploying to Kubernetes..."
    
    cd "$PROJECT_ROOT"
    
    # Create namespace if not exists
    kubectl create namespace freqtrade --dry-run=client -o yaml | kubectl apply -f -
    
    # Update image in deployment
    REGISTRY=${DOCKER_REGISTRY:-"docker.io"}
    REPO=${DOCKER_REPO:-"yourusername/freqtrade"}
    
    sed -i.bak "s|image: your-registry/freqtrade:latest|image: ${REGISTRY}/${REPO}:latest|g" \
        kubernetes/deployment.yaml
    
    # Apply Kubernetes manifests
    kubectl apply -f kubernetes/deployment.yaml
    
    # Wait for deployment
    log_info "Waiting for deployment to complete..."
    kubectl rollout status deployment/freqtrade -n freqtrade --timeout=10m
    
    log_info "Kubernetes deployment complete ✓"
}

# Setup monitoring
setup_monitoring() {
    log_step "Setting up monitoring..."
    
    # Install Prometheus & Grafana using Helm
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    
    # Add Helm repos
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    # Install Prometheus
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --set prometheus.prometheusSpec.retention=30d \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi
    
    log_info "Monitoring setup complete ✓"
}

# Get access information
get_access_info() {
    log_step "Fetching access information..."
    
    echo ""
    echo "=========================================="
    echo "🎉 DEPLOYMENT COMPLETE!"
    echo "=========================================="
    echo ""
    
    # Get NodeBalancer IP
    echo "📍 Load Balancer IP:"
    cd "$PROJECT_ROOT/terraform/linode" && terraform output -raw load_balancer_ip
    echo ""
    echo ""
    
    # Get service endpoints
    echo "🔗 Service Endpoints:"
    kubectl get svc -n freqtrade -o wide
    echo ""
    
    # Get pods
    echo "📦 Running Pods:"
    kubectl get pods -n freqtrade
    echo ""
    
    # Get Grafana info
    echo "📊 Grafana Dashboard:"
    GRAFANA_IP=$(kubectl get svc -n monitoring prometheus-grafana -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    echo "  URL: http://${GRAFANA_IP}"
    echo "  Username: admin"
    echo "  Password: $(kubectl get secret -n monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode)"
    echo ""
    
    echo "📝 Useful Commands:"
    echo "  View logs: kubectl logs -f deployment/freqtrade -n freqtrade"
    echo "  Shell access: kubectl exec -it deployment/freqtrade -n freqtrade -- bash"
    echo "  View metrics: kubectl top pods -n freqtrade"
    echo ""
    
    echo "💰 Estimated Monthly Cost: ~\$180-240"
    echo ""
    
    echo "✅ Your Freqtrade bot is now running on Linode!"
}

# Verify deployment
verify_deployment() {
    log_step "Verifying deployment..."
    
    # Wait for service
    sleep 30
    
    # Get service URL
    SERVICE_IP=$(kubectl get svc freqtrade -n freqtrade -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    
    if [ -n "$SERVICE_IP" ]; then
        log_info "Testing API endpoint..."
        if curl -f http://${SERVICE_IP}:8080/api/v1/ping; then
            log_info "Health check passed ✓"
        else
            log_warn "Health check failed - service may still be starting"
        fi
    else
        log_warn "LoadBalancer IP not ready yet"
    fi
}

# Cleanup/destroy
destroy() {
    log_warn "This will destroy ALL Linode infrastructure!"
    read -p "Type 'yes' to confirm destruction: " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Destruction cancelled"
        exit 0
    fi
    
    cd "$PROJECT_ROOT/terraform/linode"
    terraform destroy
    
    log_info "Infrastructure destroyed"
}

# Main menu
main() {
    echo "=========================================="
    echo "   Freqtrade Linode Deployment Script    "
    echo "=========================================="
    echo ""
    echo "Select an option:"
    echo "  1) Full deployment (infrastructure + app)"
    echo "  2) Deploy infrastructure only"
    echo "  3) Deploy application only"
    echo "  4) Build and push image"
    echo "  5) Setup monitoring"
    echo "  6) Get access information"
    echo "  7) Destroy infrastructure"
    echo "  8) Exit"
    echo ""
    read -p "Enter option (1-8): " option
    
    case $option in
        1)
            check_prerequisites
            setup_linode_cli
            build_image
            push_image
            deploy_infrastructure
            configure_kubectl
            deploy_kubernetes
            setup_monitoring
            verify_deployment
            get_access_info
            ;;
        2)
            check_prerequisites
            setup_linode_cli
            deploy_infrastructure
            configure_kubectl
            ;;
        3)
            check_prerequisites
            configure_kubectl
            deploy_kubernetes
            verify_deployment
            ;;
        4)
            check_prerequisites
            build_image
            push_image
            ;;
        5)
            check_prerequisites
            configure_kubectl
            setup_monitoring
            ;;
        6)
            get_access_info
            ;;
        7)
            destroy
            ;;
        8)
            log_info "Exiting..."
            exit 0
            ;;
        *)
            log_error "Invalid option"
            exit 1
            ;;
    esac
}

# Run main
main
