output "registry_endpoint" {
  description = "Container registry endpoint"
  value       = module.registry.endpoint
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}
