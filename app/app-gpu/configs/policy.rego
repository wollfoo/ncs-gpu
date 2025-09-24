package app_gpu.authz

default allow = false

allow {
  input.role == "operator"
  input.action == "submit_job"
}

allow {
  input.role == "observer"
  input.action == "read_metrics"
}
