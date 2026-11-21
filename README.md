# devops-lab

A production-shaped Kubernetes platform that runs entirely on one Windows PC, for free:
WSL2 → Docker Engine → kind (3 nodes) → MetalLB + Gateway API (Envoy) → Prometheus/Grafana → Argo CD (GitOps)
→ GitHub Actions on a self-hosted runner.

```
 Windows browser                                   WSL2 (Ubuntu 24.04)
 http://*.localtest.me ──► localhost:80 ──► kind node "lab-control-plane" :80
                                              │ hostPort 80 → 10080
                                              ▼
                         ┌──────────── Envoy proxy (Gateway "lab") ─────────────┐
                         │  HTTPRoutes by hostname, per-request L7 balancing    │
                         └──┬──────────────┬──────────────┬──────────────┬──────┘
                            ▼              ▼              ▼              ▼
                       echo (x3)        Grafana       Prometheus      Argo CD
                     spread over      (monitoring)   Alertmanager    (argocd) ◄── GitHub repo (main)
                     both workers                                        │ syncs apps/
 MetalLB: the same Gateway also gets 172.18.255.200 (L2), reachable from WSL.
```

## Quick start (inside WSL)

```bash
./lab up          # cluster + whole platform + apps; idempotent, run it again to converge
./lab status      # nodes, gateway, routes, unhealthy pods, URLs
./lab passwords   # Grafana / Argo CD admin passwords
./lab help        # every command
```

| URL | What |
|---|---|
| http://echo.localtest.me/hostname | demo app, answers with the pod name |
| http://grafana.localtest.me | dashboards (admin / `./lab passwords`) |
| http://prometheus.localtest.me | metrics, targets, alerts |
| http://alertmanager.localtest.me | alert routing |
| http://argocd.localtest.me | GitOps (admin / `./lab passwords`) |

`*.localtest.me` is public DNS that points to 127.0.0.1, so no hosts-file edits.

## Layout

| Path | Owner | Content |
|---|---|---|
| `lab` | everyone | the single entry point; pinned platform versions at the top |
| `cluster/kind.yaml` | platform | node layout, port mappings |
| `platform/` | platform | MetalLB pool, Gateway + EnvoyProxy, monitoring and Argo CD values and routes |
| `apps/` | app teams | workloads; delivered by Argo CD once GitOps is on |
| `gitops/root.yaml` | platform | the Argo CD root Application that watches `apps/` |
| `.github/workflows/ci.yml` | platform | `./lab check` on every PR, on the self-hosted runner |

## Lessons

New to a piece of this stack? Start with the [lessons](docs/lessons/README.md): every layer explained in
plain words, each with an animation. The handbooks below are the deep reference.

## Handbooks

1. [Host: WSL2, Docker, credentials](docs/handbook/01-host.md)
2. [Cluster: kind](docs/handbook/02-cluster.md)
3. [Traffic: MetalLB, Gateway API, Envoy, scheduling](docs/handbook/03-traffic.md)
4. [Observability: Prometheus, Grafana, Alertmanager](docs/handbook/04-observability.md)
5. [GitOps: Argo CD](docs/handbook/05-gitops.md)
6. [CI and the delivery flow](docs/handbook/06-ci.md)
7. [Troubleshooting runbook](docs/handbook/07-troubleshooting.md)
