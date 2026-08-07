{{/* Helper template functions */}}
{{- define "devsecops-app.name" -}}
devsecops-app
{{- end -}}

{{- define "devsecops-app.fullname" -}}
{{ printf "%s" (include "devsecops-app.name" .) }}
{{- end -}}
