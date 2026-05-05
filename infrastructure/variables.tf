variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "do_region" {
  description = "DigitalOcean region"
  type        = string
  default     = "sgp1"
}

variable "project_name" {
  description = "Project name used for naming resources"
  type        = string
  default     = "flood-management"
}
