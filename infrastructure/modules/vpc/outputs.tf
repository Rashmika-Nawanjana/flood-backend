output "vpc_id" {
  description = "VPC ID"
  value       = digitalocean_vpc.main.id
}

output "vpc_name" {
  description = "VPC name"
  value       = digitalocean_vpc.main.name
}
