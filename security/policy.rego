package kubernetes.policy

# OPA policy to enforce Kubernetes Deployment/Pod security constraints
# - Containers must not run as root (securityContext.runAsNonRoot == true)
# - Image tag "latest" is disallowed
# - Each container must declare resources.requests and resources.limits (cpu or memory)

# Admission review entrypoint
package kubernetes.admission

import data.kubernetes.namespaces

# Deny by default if any check fails
deny[msg] {
  some i
  input.request.object: obj
  containers := get_containers(obj)
  cont := containers[i]
  reason := []
  not run_as_non_root(cont)
  msg = sprintf("container '%s' in %s/%s must set securityContext.runAsNonRoot: true", [cont.name, obj.metadata.namespace, obj.metadata.name])
}

deny[msg] {
  some i
  input.request.object: obj
  containers := get_containers(obj)
  cont := containers[i]
  image_latest(cont)
  msg = sprintf("container '%s' in %s/%s is using the 'latest' image tag which is disallowed: %s", [cont.name, obj.metadata.namespace, obj.metadata.name, cont.image])
}

deny[msg] {
  some i
  input.request.object: obj
  containers := get_containers(obj)
  cont := containers[i]
  not resources_defined(cont)
  msg = sprintf("container '%s' in %s/%s must set resource requests and limits", [cont.name, obj.metadata.namespace, obj.metadata.name])
}

# Helpers
get_containers(obj) = all_containers {
  # Support Pod template (Deployment, DaemonSet, StatefulSet) and Pod objects
  all_containers = (
    obj.spec.template.spec.containers
  )
  all_containers != null
} else = pods_containers {
  pods_containers = obj.spec.containers
}

# runAsNonRoot must be true either at container or pod level
run_as_non_root(cont) {
  cont.securityContext.runAsNonRoot == true
} else {
  # check pod-level securityContext
  input.request.object.spec.template.spec.securityContext.runAsNonRoot == true
}

# detect latest tag (note: image names without a tag may implicitly be 'latest')
image_latest(cont) {
  img := cont.image
  # If image contains ':' check tag
  contains(img, ":")
  parts := split(img, ":")
  tag := parts[count(parts)-1]
  lower(tag) == "latest"
}

image_latest(cont) {
  img := cont.image
  # No tag provided -> implicit latest
  not contains(img, ":")
}

# resources must include both requests and limits with at least one resource inside
resources_defined(cont) {
  rc := cont.resources
  rc.requests
  rc.limits
  # ensure at least one cpu or memory present in requests and limits
  (rc.requests.cpu != null or rc.requests.memory != null)
  (rc.limits.cpu != null or rc.limits.memory != null)
}

# helper: contains
contains(x, y) { indexof(x, y) >= 0 }

