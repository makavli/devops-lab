# 4. Observability: Prometheus, Grafana, Alertmanager

Installed by `./lab up` as **kube-prometheus-stack** (release `kps`, namespace `monitoring`),
values in `platform/monitoring/values.yaml`.

## Pieces
| Component | Job |
|---|---|
| Prometheus Operator | turns CRDs (ServiceMonitor, PodMonitor, PrometheusRule) into Prometheus config |
| Prometheus | scrapes every 30 s, stores 3 days (`retention`), evaluates alert rules |
| Alertmanager | groups, silences and routes alerts (no receivers configured yet) |
| Grafana | dashboards; ships ~30 for nodes, pods, workloads, API server, kubelet, CoreDNS |
| node-exporter | DaemonSet, host metrics per node |
| kube-state-metrics | object state as metrics (replicas wanted vs ready, pod phase, restarts) |

## How scraping is wired
Prometheus does not discover things by itself here: a **ServiceMonitor** (selects a Service, then its
endpoints) or a **PodMonitor** (selects pods directly) tells the operator what to scrape.
`*SelectorNilUsesHelmValues: false` makes Prometheus pick up monitors from every namespace without the
`release: kps` label, which is why the Envoy PodMonitor (`platform/monitoring/routes.yaml`) and Argo CD's
ServiceMonitors work.

Check targets: http://prometheus.localtest.me/targets, or
```bash
kubectl get --raw '/api/v1/namespaces/monitoring/services/kps-kube-prometheus-stack-prometheus:9090/proxy/api/v1/targets?state=active' | jq -r '.data.activeTargets[] | [.health, .scrapePool] | @tsv'
```

Disabled on purpose: scheduler, controller-manager, etcd and kube-proxy metrics. kind binds them to
127.0.0.1 inside the node, so they would only fire "target down" (exercise in 02-cluster.md).

## Useful PromQL
```promql
# requests per second through Envoy, per route
sum by (envoy_cluster_name) (rate(envoy_cluster_upstream_rq_total[1m]))
# 5xx ratio per route
sum by (envoy_cluster_name) (rate(envoy_cluster_upstream_rq_xx{envoy_response_code_class="5"}[5m]))
  / sum by (envoy_cluster_name) (rate(envoy_cluster_upstream_rq_total[5m]))
# p95 upstream latency (ms)
histogram_quantile(0.95, sum by (le, envoy_cluster_name) (rate(envoy_cluster_upstream_rq_time_bucket[5m])))
# pods restarting
increase(kube_pod_container_status_restarts_total[15m]) > 0
# memory vs limit per container
container_memory_working_set_bytes{container!=""} / on(namespace,pod,container) kube_pod_container_resource_limits{resource="memory"}
# Argo CD apps not Synced
argocd_app_info{sync_status!="Synced"}
```

## Grafana
http://grafana.localtest.me, user `admin`, password from `./lab passwords`.
Start with *Kubernetes / Compute Resources / Namespace (Pods)* and *Node Exporter / Nodes*.
Community dashboards to import (Dashboards → New → Import, by ID): Argo CD, Envoy. Imported dashboards live
only in Grafana's volume; to keep one, export its JSON into a ConfigMap labelled `grafana_dashboard: "1"`
(the sidecar loads it), committed to Git.

## Alerts
Rules: http://prometheus.localtest.me/alerts. `Watchdog` always fires: it proves the pipeline works
(in prod, an external dead-man's switch pages when it stops). Your own rule, as code:
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata: { name: echo, namespace: default }
spec:
  groups:
    - name: echo
      rules:
        - alert: EchoReplicasMissing
          expr: kube_deployment_status_replicas_available{deployment="echo"} < 5
          for: 2m
          labels: { severity: warning }
          annotations: { summary: "echo has {{ $value }} of 5 replicas available" }
```

## Exercises
1. Add the rule above under `apps/echo/`, then set `replicas: 1` in Git (selfHeal undoes a `kubectl scale`),
   and watch it go Pending → Firing in Alertmanager.
2. Build a Grafana panel for the request-rate query while running a curl loop; kill a pod mid-loop.
3. Configure an Alertmanager receiver via `alertmanager.config` in values: a webhook to a small pod that logs
   what it receives. Give that pod no HTTPRoute (agnhost `netexec`, for one, also runs commands on `/shell`).
4. Load test: `kubectl run load --rm -it --image=williamyeh/hey@sha256:6e63ae9c5801204cf7abe22c9ddf82d1bcbc7140ffd206a9bd83a8a643dcd6f2 -- -z 60s -c 20 http://echo.default/hostname`,
   then find the CPU throttling in Grafana. The third-party image is pinned by digest: a tag can be moved.
