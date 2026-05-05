# Flood Management System - Infrastructure

Terraform infrastructure for the Smart Flood Management System (Group A4).

## Structure

```
infrastructure/
├── main.tf           # Root module, provider config
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── .gitignore        # Excludes state files and secrets
└── modules/
    ├── ecr/          # ECR repositories for all services
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── vpc/          # VPC, subnets, security groups
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Resources Provisioned

### ECR Module
- 6 ECR repositories (one per service):
  - flood-management/flood-api
  - flood-management/flood-auth
  - flood-management/flood-frontend
  - flood-management/flood-sensor-service
  - flood-management/flood-intelligence-service
  - flood-management/flood-zone-service
- Lifecycle policy: keeps last 5 images per repo

### VPC Module
- VPC (10.0.0.0/16)
- 1 public subnet
- 2 private subnets
- Internet Gateway
- Route tables
- Security group (ports: 80, 443, 8000, 8001, 8080)

## Usage

### Prerequisites
- Terraform >= 1.0
- AWS CLI configured (`aws configure`)
- AWS account with sufficient permissions

### Commands

```bash
# Initialise (download providers)
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply

# Destroy all resources
terraform destroy
```

## Services

| Service | ECR Repo |
|---|---|
| Main API | flood-management/flood-api |
| Auth Service | flood-management/flood-auth |
| Frontend | flood-management/flood-frontend |
| Sensor Service | flood-management/flood-sensor-service |
| Intelligence Service | flood-management/flood-intelligence-service |
| Zone Service | flood-management/flood-zone-service |
