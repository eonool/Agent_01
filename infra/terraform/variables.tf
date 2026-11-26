variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Cloud Run / Scheduler region"
  type        = string
  default     = "us-central1"
}

variable "model_location" {
  description = "Vertex AI model location"
  type        = string
  default     = "global"
}

variable "firestore_location" {
  description = "Firestore database location"
  type        = string
  default     = "nam5"
}

variable "image" {
  description = "Container image for the agent (built from the repo Dockerfile)"
  type        = string
}

variable "time_zone" {
  description = "Scheduler time zone"
  type        = string
  default     = "Asia/Seoul"
}
