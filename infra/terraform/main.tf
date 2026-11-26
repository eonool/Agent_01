# Infrastructure for Agent_01 (declarative IaC).
# terraform init && terraform apply -var="project_id=<project>" -var="image=<image>"

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  services = [
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "firestore.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "cloudscheduler.googleapis.com",
    "gmail.googleapis.com",
    "docs.googleapis.com",
  ]
  runtime_roles = [
    "roles/aiplatform.user",
    "roles/datastore.user",
    "roles/cloudtrace.agent",
    "roles/logging.logWriter",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

# Dedicated least-privilege runtime identity.
resource "google_service_account" "agent" {
  account_id   = "agent-01-runtime"
  display_name = "Agent_01 runtime"
}

resource "google_project_iam_member" "agent_roles" {
  for_each = toset(local.runtime_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.agent.email}"
}

# Secret Manager: OAuth client and token. Values are added out-of-band, never in code.
resource "google_secret_manager_secret" "oauth" {
  for_each  = toset(["agent01-oauth-client", "agent01-oauth-token"])
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each  = google_secret_manager_secret.oauth
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_secret_manager_secret_iam_member" "token_writer" {
  secret_id = google_secret_manager_secret.oauth["agent01-oauth-token"].id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.agent.email}"
}

# Persistent long-term memory.
resource "google_firestore_database" "memory" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "agent" {
  name                = "agent-01"
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.agent.email
    containers {
      image = var.image
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.model_location
      }
      env {
        name  = "AGENT01_MEMORY_BACKEND"
        value = "firestore"
      }
      env {
        name  = "AGENT01_OAUTH_CLIENT_SECRET"
        value = "agent01-oauth-client"
      }
      env {
        name  = "AGENT01_OAUTH_TOKEN_SECRET"
        value = "agent01-oauth-token"
      }
    }
  }
  depends_on = [google_project_service.apis]
}

# Bi-weekly trigger: every Monday 09:00; the agent skips odd ISO weeks.
resource "google_cloud_scheduler_job" "biweekly" {
  name      = "agent-01-biweekly"
  schedule  = "0 9 * * 1"
  time_zone = var.time_zone
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.agent.uri}/run"
    headers     = { "Content-Type" = "application/json" }
    body = base64encode(jsonencode({
      app_name    = "agent_01"
      user_id     = "scheduler"
      session_id  = "biweekly"
      new_message = { role = "user", parts = [{ text = "Prepare my bi-weekly review." }] }
    }))
    oidc_token {
      service_account_email = google_service_account.agent.email
    }
  }
  depends_on = [google_project_service.apis]
}
