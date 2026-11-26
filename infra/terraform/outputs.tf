output "service_url" {
  value = google_cloud_run_v2_service.agent.uri
}

output "runtime_service_account" {
  value = google_service_account.agent.email
}
