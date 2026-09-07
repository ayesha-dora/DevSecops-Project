# Monitoring Stack Check & New Dashboard — 2026-09-08

Done via SSH into the AWS EC2 instance (`3.7.244.169`, user `ubuntu`) running your
DevSecOps stack, using `Devops-key.pem`. Nothing was changed until the last section
below — everything before that was read-only inspection.

## 1. Health check: is Grafana ↔ Prometheus ↔ Loki actually wired up?

**Yes — confirmed end to end, not just "containers are running":**

- `grafana`, `prometheus`, `loki`, `promtail` all on the same Docker network
  (`devsecops-project_devsecops`), so they can reach each other by container name.
- `monitoring/grafana-provisioning/datasources/datasources.yml` provisions two
  datasources named exactly `Prometheus` (`http://prometheus:9090`) and `Loki`
  (`http://loki:3100`) — correct, and matching what the dashboard JSON expects.
- From **inside** the Grafana container: `prometheus:9090/-/healthy` → healthy,
  `loki:3100/ready` → ready. So Grafana can genuinely talk to both, not just "both
  happen to be up".
- Prometheus is actively scraping its one configured job, `devsecops-app` (target
  `devsecops-app:5000/metrics`), and that target reports `up`.
- Loki has ingested log streams (`job` label) from all 9 containers, including
  `devsecops-app`, `grafana`, `prometheus`, `jenkins`, `sonarqube`, `mlflow` —
  Promtail is actively shipping logs, not just running.
- One transient `HTTP 503` from Loki's `/ready` during a checkpoint/compaction
  cycle was seen once, then resolved on its own within the same minute — normal
  Loki behavior, not a fault.

**Not part of this stack but noticed in passing:** the `owasp-zap` container is
running but reports Docker health status `unhealthy`. Not touched — flagging it
in case you want it looked at separately.

## 2. What Prometheus is actually scraping

`monitoring/prometheus.yml` defines exactly one active job:

```yaml
- job_name: 'devsecops-app'
  metrics_path: /metrics
  static_configs:
    - targets: ['devsecops-app:5000']
```

(A `jenkins` job exists in the file but is commented out — the stock Jenkins image
doesn't expose Prometheus metrics without a plugin that isn't installed.)

The `/metrics` endpoint on `devsecops-app` exposes:
- `http_requests_total`, `http_request_duration_seconds` — your app's own metrics
  (no samples yet — no requests have hit those code paths since the container
  started)
- Standard Python process metrics: `python_gc_*` (GC activity),
  `process_resident_memory_bytes` / `process_virtual_memory_bytes` (memory),
  `process_cpu_seconds_total` (CPU), `process_open_fds` / `process_max_fds` (file
  descriptors), `process_start_time_seconds` (uptime), `python_info` (runtime
  version)

## 3. New dashboard: `DevSecOps App - Full Prometheus Metrics`

The **existing** dashboard (`devsecops-overview.json`, uid `devsecops-basic`) only
graphs `http_requests_total` and a Loki log panel — it ignores everything else
Prometheus scrapes.

Added a new file, **`monitoring/grafana-provisioning/dashboards/files/devsecops-app-metrics.json`**
(uid `devsecops-app-metrics`), with 10 panels covering every metric family listed
above:

1. HTTP Requests Rate
2. HTTP Request Duration (p50/p95/p99)
3. Process CPU Usage
4. Process Memory (RSS vs Virtual)
5. Open File Descriptors (used vs max)
6. Python GC Collections Rate (by generation)
7. Python GC Objects Collected Rate (by generation)
8. Python GC Uncollectable Objects
9. Process Uptime (stat)
10. Python Runtime Version (stat)

It sits alongside the original dashboard (doesn't replace or modify it) and uses
the same provisioning format/schema version so Grafana's file-provisioner picks
it up the same way.

## 4. Deployment (the only step that touched the live instance)

With your explicit go-ahead:

1. `scp`'d the new JSON to the VM:
   `~/DevSecops-Project/monitoring/grafana-provisioning/dashboards/files/devsecops-app-metrics.json`
2. `docker restart grafana`
3. Verified after restart:
   - Container back to `Up`, `GET /api/health` → `200 OK`, `database: ok`
   - File confirmed present inside the container at
     `/etc/grafana/provisioning/dashboards/files/`
   - Grafana logs show a clean provisioning cycle right after restart:
     `starting to provision dashboards` → `finished to provision dashboards`,
     with no error/warning in between (a bad dashboard JSON logs an ERROR line
     here — there wasn't one)

**What I could not verify directly:** I don't have your Grafana admin login, so I
couldn't hit the authenticated API or UI to screenshot the panel itself (and
didn't try guessing credentials). To see it with your own eyes:

- Open `http://3.7.244.169:3000` in a browser, log in, and look for
  **"DevSecOps App - Full Prometheus Metrics"** in the dashboard list.
- If a panel shows "No data" for `http_requests_total`/`http_request_duration_seconds`,
  that's expected — hit the app a few times first so it has requests to count.

## Rollback

If you want it gone, delete the one new file and restart Grafana — nothing else
was touched:

```bash
ssh -i Devops-key.pem ubuntu@3.7.244.169 \
  "rm ~/DevSecops-Project/monitoring/grafana-provisioning/dashboards/files/devsecops-app-metrics.json && docker restart grafana"
```
