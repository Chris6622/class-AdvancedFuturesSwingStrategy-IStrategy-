# Terraform configuration for Linode deployment
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    linode = {
      source  = "linode/linode"
      version = "~> 2.9"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.9"
    }
  }
  
  backend "s3" {
    bucket = "freqtrade-terraform-state"
    key    = "linode/terraform.tfstate"
    region = "us-east-1"
    # Use Linode Object Storage compatible with S3
    endpoint = "us-east-1.linodeobjects.com"
    skip_credentials_validation = true
    skip_metadata_api_check = true
    skip_region_validation = true
  }
}

provider "linode" {
  token = var.linode_token
}

# Variables
variable "linode_token" {
  description = "Linode API token"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "Linode region"
  type        = string
  default     = "us-east"  # Options: us-east, us-west, eu-central, ap-south, etc.
}

variable "cluster_name" {
  description = "LKE cluster name"
  type        = string
  default     = "freqtrade-cluster"
}

variable "k8s_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "redis_password" {
  description = "Redis password"
  type        = string
  sensitive   = true
}

# Linode Kubernetes Engine (LKE) Cluster
resource "linode_lke_cluster" "freqtrade" {
  label       = var.cluster_name
  k8s_version = var.k8s_version
  region      = var.region
  
  tags = [
    "freqtrade",
    var.environment,
    "trading-bot"
  ]

  # General purpose node pool
  pool {
    type  = "g6-standard-2"  # 2 vCPU, 4GB RAM - $36/month
    count = 2

    autoscaler {
      min = 1
      max = 4
    }
  }

  # Dedicated node pool for trading
  pool {
    type  = "g6-standard-4"  # 4 vCPU, 8GB RAM - $72/month
    count = 1

    autoscaler {
      min = 1
      max = 2
    }
  }
}

# Managed PostgreSQL Database
resource "linode_database_postgresql" "freqtrade" {
  label         = "${var.cluster_name}-postgres"
  engine_id     = "postgresql/15.2"
  region        = var.region
  type          = "g6-nanode-1"  # 1GB RAM - $15/month
  
  cluster_size  = 3  # High availability with 3 nodes
  replication_type = "asynch"
  
  ssl_connection = true
  
  encrypted = true

  updates {
    day_of_week   = "sunday"
    duration      = 3
    frequency     = "weekly"
    hour_of_day   = 3
    week_of_month = null
  }
}

# Managed MySQL (alternative if you prefer MySQL)
# resource "linode_database_mysql" "freqtrade" {
#   label         = "${var.cluster_name}-mysql"
#   engine_id     = "mysql/8.0.30"
#   region        = var.region
#   type          = "g6-nanode-1"
#   cluster_size  = 3
# }

# Object Storage for backups
resource "linode_object_storage_bucket" "backups" {
  cluster = "${var.region}-1"
  label   = "${var.cluster_name}-backups"

  lifecycle_rule {
    enabled = true
    id      = "delete-old-backups"
    
    expiration {
      days = 90
    }
  }

  versioning = true
}

resource "linode_object_storage_key" "backups" {
  label = "${var.cluster_name}-backup-key"

  bucket_access {
    bucket_name = linode_object_storage_bucket.backups.label
    cluster     = linode_object_storage_bucket.backups.cluster
    permissions = "read_write"
  }
}

# Block Storage for persistent data
resource "linode_volume" "freqtrade_data" {
  label  = "${var.cluster_name}-data"
  region = var.region
  size   = 50  # 50GB - $5/month

  tags = [
    "freqtrade",
    "persistent-data"
  ]
}

resource "linode_volume" "hyperopt_results" {
  label  = "${var.cluster_name}-hyperopt"
  region = var.region
  size   = 20  # 20GB - $2/month

  tags = [
    "freqtrade",
    "hyperopt-results"
  ]
}

# Firewall
resource "linode_firewall" "freqtrade" {
  label = "${var.cluster_name}-firewall"

  inbound {
    label    = "allow-https"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "443"
    ipv4     = ["0.0.0.0/0"]
    ipv6     = ["::/0"]
  }

  inbound {
    label    = "allow-http"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "80"
    ipv4     = ["0.0.0.0/0"]
    ipv6     = ["::/0"]
  }

  inbound {
    label    = "allow-k8s-api"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "6443"
    ipv4     = ["0.0.0.0/0"]
  }

  inbound_policy = "DROP"

  outbound {
    label    = "allow-all-outbound"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "1-65535"
    ipv4     = ["0.0.0.0/0"]
    ipv6     = ["::/0"]
  }

  outbound_policy = "ACCEPT"

  linodes = []
}

# NodeBalancer (Load Balancer)
resource "linode_nodebalancer" "freqtrade" {
  label  = "${var.cluster_name}-lb"
  region = var.region

  tags = [
    "freqtrade",
    "load-balancer"
  ]
}

resource "linode_nodebalancer_config" "https" {
  nodebalancer_id = linode_nodebalancer.freqtrade.id
  port            = 443
  protocol        = "https"
  check           = "http"
  check_path      = "/api/v1/ping"
  check_attempts  = 3
  check_timeout   = 3
  check_interval  = 5
  stickiness      = "table"
  algorithm       = "leastconn"

  ssl_cert = var.ssl_cert
  ssl_key  = var.ssl_key
}

resource "linode_nodebalancer_config" "http" {
  nodebalancer_id = linode_nodebalancer.freqtrade.id
  port            = 80
  protocol        = "http"
  check           = "http"
  check_path      = "/api/v1/ping"
  check_attempts  = 3
  check_timeout   = 3
  check_interval  = 5
  stickiness      = "table"
  algorithm       = "roundrobin"
}

# Kubernetes provider configuration
provider "kubernetes" {
  host                   = linode_lke_cluster.freqtrade.api_endpoints[0]
  token                  = linode_lke_cluster.freqtrade.token
  cluster_ca_certificate = base64decode(linode_lke_cluster.freqtrade.kubeconfig)
}

# Create Kubernetes namespace
resource "kubernetes_namespace" "freqtrade" {
  metadata {
    name = "freqtrade"
    labels = {
      name        = "freqtrade"
      environment = var.environment
    }
  }

  depends_on = [linode_lke_cluster.freqtrade]
}

# Kubernetes secrets
resource "kubernetes_secret" "freqtrade" {
  metadata {
    name      = "freqtrade-secrets"
    namespace = kubernetes_namespace.freqtrade.metadata[0].name
  }

  data = {
    postgres-host     = linode_database_postgresql.freqtrade.host
    postgres-port     = tostring(linode_database_postgresql.freqtrade.port)
    postgres-password = var.db_password
    redis-password    = var.redis_password
    s3-access-key     = linode_object_storage_key.backups.access_key
    s3-secret-key     = linode_object_storage_key.backups.secret_key
  }

  type = "Opaque"
}

# Outputs
output "cluster_id" {
  description = "LKE cluster ID"
  value       = linode_lke_cluster.freqtrade.id
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = linode_lke_cluster.freqtrade.api_endpoints[0]
  sensitive   = true
}

output "kubeconfig" {
  description = "Kubeconfig file content"
  value       = linode_lke_cluster.freqtrade.kubeconfig
  sensitive   = true
}

output "database_host" {
  description = "PostgreSQL database host"
  value       = linode_database_postgresql.freqtrade.host
}

output "database_port" {
  description = "PostgreSQL database port"
  value       = linode_database_postgresql.freqtrade.port
}

output "load_balancer_ip" {
  description = "NodeBalancer public IP"
  value       = linode_nodebalancer.freqtrade.ipv4
}

output "backup_bucket" {
  description = "Object storage bucket for backups"
  value       = "${linode_object_storage_bucket.backups.cluster}.linodeobjects.com/${linode_object_storage_bucket.backups.label}"
}

output "backup_access_key" {
  description = "S3-compatible access key for backups"
  value       = linode_object_storage_key.backups.access_key
  sensitive   = true
}

output "backup_secret_key" {
  description = "S3-compatible secret key for backups"
  value       = linode_object_storage_key.backups.secret_key
  sensitive   = true
}

# Variables for SSL (optional - can use cert-manager instead)
variable "ssl_cert" {
  description = "SSL certificate content"
  type        = string
  default     = ""
}

variable "ssl_key" {
  description = "SSL private key content"
  type        = string
  default     = ""
  sensitive   = true
}

# Cost estimation output
output "estimated_monthly_cost" {
  description = "Estimated monthly cost in USD"
  value = <<-EOT
    LKE Cluster Nodes:
      - 2x g6-standard-2: $72/month
      - 1x g6-standard-4: $72/month
    Managed PostgreSQL: $15/month (1GB) to $60/month (8GB)
    Block Storage: $7/month (70GB total)
    NodeBalancer: $10/month
    Object Storage: $5/month (250GB included)
    
    Total Estimated: ~$180-240/month
    
    Note: Costs may vary based on:
    - Actual usage and scaling
    - Data transfer (1TB/month included per Linode)
    - Additional storage
    - Backup retention
  EOT
}
