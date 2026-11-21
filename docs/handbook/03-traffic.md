# 3. Traffic: MetalLB, Gateway API, Envoy, scheduling

## The request path
```
Windows/WSL ─► localhost:80 ─► lab-control-plane :80 ─► Envoy pod hostPort 80 → :10080
             ─► route match on Host header (HTTPRoute) ─► pod IP from EndpointSlices (no kube-proxy hop)
WSL only    ─► 172.18.255.200:80 (MetalLB) ─► a worker answers ARP ─► kube-proxy ─► Envoy ─► pods
```

## MetalLB (`platform/metallb/pool.yaml`)
- **L2 mode**: one speaker is elected per IP and answers ARP for it; failover = another speaker sends
  gratuitous ARP. No real load spreading at L2: one node takes all traffic for an IP. BGP mode
  (ECMP across routers) is what spreads it in a datacenter.
- The pool is the top of the kind Docker subnet, away from node IPs Docker assigns from the bottom.
- Gotcha: kind labels the control plane `node.kubernetes.io/exclude-from-external-load-balancers`,
  so MetalLB never announces from it. With `externalTrafficPolicy: Local` (Envoy Gateway's default)
  only Envoy's own node may announce, so the IP goes dead. The lab uses `Cluster`: any worker announces and
  kube-proxy forwards. Trade-off: `Local` keeps the client source IP and saves a hop; `Cluster` SNATs.

## Gateway API (`platform/envoy-gateway/gateway.yaml`)
Role-oriented, the successor of Ingress (ingress-nginx is retired upstream):

| Object | Owner | Here |
|---|---|---|
| GatewayClass | infra provider | `envoy` → Envoy Gateway controller, parameters in EnvoyProxy `kind` |
| Gateway | platform team | `lab` in `default`, HTTP :80, routes from all namespaces |
| HTTPRoute | app team | one per app, matched on hostname |

EnvoyProxy settings kind needs, each one a lesson:
- `nodeSelector` + toleration: run on the only node with published ports.
- hostPort `80 → 10080`: Envoy is non-root, so EG shifts privileged listener ports by +10000.
- Rollout strategy `maxSurge: 0, maxUnavailable: 1`: a surge pod could never bind the same hostPort.
  `type: Recreate` would also do it, but the API server rejects switching to it while the live
  Deployment still carries `rollingUpdate` defaults (server-side apply keeps them).

Inspect:
```bash
kubectl get gatewayclass,gateway,httproute -A
kubectl describe httproute echo          # Accepted / ResolvedRefs conditions
kubectl -n envoy-gateway-system logs deploy/envoy-gateway | grep -i error
```

## Load balancing
- Envoy watches EndpointSlices and balances **per request** (L7). kube-proxy balances **per connection**
  (L4): with keep-alive or gRPC, one client sticks to one pod. A classic production surprise.
- Policy here: **ROUND_ROBIN** (Envoy Gateway's default). Each Envoy worker thread keeps its own cursor, so
  a sequential curl loop with new connections can come out uneven (10/13/7 over 30 requests is normal).
- Read the live config:
  ```bash
  P=$(kubectl -n envoy-gateway-system get pod -l app.kubernetes.io/component=proxy -o name)
  kubectl -n envoy-gateway-system port-forward $P 19000 &
  curl -s localhost:19000/config_dump | grep -A2 '"name": "httproute/default/echo'
  curl -s localhost:19000/clusters | grep echo     # per-endpoint health, active requests
  ```
- Change it per route with a policy (add it under `apps/echo/` so Argo CD delivers it):
  ```yaml
  apiVersion: gateway.envoyproxy.io/v1alpha1
  kind: BackendTrafficPolicy
  metadata: { name: echo, namespace: default }
  spec:
    targetRefs: [{ group: gateway.networking.k8s.io, kind: HTTPRoute, name: echo }]
    loadBalancer: { type: LeastRequest }   # or Random, ConsistentHash (sticky by header/cookie/source IP)
  ```

Measure: `for i in $(seq 300); do curl -s echo.localtest.me/hostname; echo; done | sort | uniq -c`

## Scheduling: topology spread
`apps/echo/echo.yaml` spreads replicas across nodes with `maxSkew: 1`. Two fields matter:
- `nodeTaintsPolicy: Honor`: by default tainted nodes **count** as domains. The control plane (0 pods,
  never schedulable) becomes the global minimum, every placement breaks the skew, and a rollout can deadlock
  (at 3 replicas the default 25% `maxUnavailable` rounds down to 0, so no old pod can leave).
- `matchLabelKeys: [pod-template-hash]`: count only the new ReplicaSet during a rollout.

Diagnose Pending pods with `kubectl get events --field-selector involvedObject.name=<pod>`: the scheduler
explains every node it rejected.

## Exercises
1. `kubectl scale deploy/echo --replicas=6` and watch the spread; then `kubectl cordon lab-worker` and scale again.
2. Kill pods during a 300-request loop: count non-200s. Then add a `preStop: sleep 5` and compare
   (endpoint removal and SIGTERM race each other).
3. Make one pod slow (a second Deployment with the `app: echo` label and `limits: { cpu: 5m }`), load it with
   `hey` (04-observability.md), and compare p95 latency under ROUND_ROBIN vs `LeastRequest`.
4. Add a second route by path (`/v2` → another Deployment) and a weighted canary (`backendRefs` with `weight`).
