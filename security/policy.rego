package kubernetes.admission

# Reject containers that:
# - do not have runAsNonRoot set to true (container or pod-level)
# - use :latest tag or have no explicit tag (implicit latest)
# - lack both resource requests and limits

deny[msg] {
  containers := get_containers(input.request.object)
  some i
  cont := containers[i]
  not run_as_non_root(cont, input.request.object)
  msg = sprintf("container '%s' in %s/%s must set securityContext.runAsNonRoot: true", [cont.name, input.request.object.metadata.namespace, input.request.object.metadata.name])
}

deny[msg] {
  containers := get_containers(input.request.object)
  some i
  cont := containers[i]
  image_latest(cont)
  msg = sprintf("container '%s' in %s/%s is using the 'latest' image tag: %s", [cont.name, input.request.object.metadata.namespace, input.request.object.metadata.name, cont.image])
}

deny[msg] {
  containers := get_containers(input.request.object)
  some i
  cont := containers[i]
  not resources_defined(cont)
  msg = sprintf("container '%s' in %s/%s must set resource requests and limits", [cont.name, input.request.object.metadata.namespace, input.request.object.metadata.name])
}

# Helpers
get_containers(obj) = containers {
  containers := obj.spec.containers
  containers != null
} else = containers {
  containers := obj.spec.template.spec.containers
  containers != null
}

run_as_non_root(cont, obj) {
  cont.securityContext.runAsNonRoot == true
} else {
  obj.spec.securityContext != null
  obj.spec.securityContext.runAsNonRoot == true
} else {
  obj.spec.template.spec.securityContext != null
  obj.spec.template.spec.securityContext.runAsNonRoot == true
}

image_latest(cont) {
  img := cont.image
  not contains(img, ":")
} else {
  img := cont.image
  parts := split(img, ":")
  tag := parts[count(parts)-1]
  lower(trim(tag)) == "latest"
}

resources_defined(cont) {
  rc := cont.resources
  rc.requests
  rc.limits
  (rc.requests.cpu != null || rc.requests.memory != null)
  (rc.limits.cpu != null || rc.limits.memory != null)
}

contains(x, y) { indexof(x, y) >= 0 }
