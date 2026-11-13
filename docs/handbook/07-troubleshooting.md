# 7. Troubleshooting runbook

First moves, in order: `./lab status` → `kubectl get events -A --sort-by=.lastTimestamp | tail -20`
→ `kubectl describe` the object → logs of the controller that owns it.

| Symptom | Cause | Fix |
|---|---|---|
| `wsl` fails `Wsl/0x80070422` | WSLService disabled | admin PowerShell: `Set-Service WSLService -StartupType Automatic; Start-Service WSLService` |
| `apt update`: `Type 'dev' is not known` / `Malformed stanza 2` | typo / blank line in a deb822 file | `Types: deb`, no blank lines inside a stanza |
| `permission denied ... docker.sock` | group added but session old | `wsl --terminate Ubuntu-24.04`, re-enter |
| kind node fails, `too many open files` | inotify limits | `/etc/sysctl.d/99-kind.conf`, `sudo sysctl --system` |
| Pod Pending, "didn't match pod topology spread constraints" | tainted node counted as a domain | `nodeTaintsPolicy: Honor` (03-traffic.md) |
| `*.localtest.me` returns 000 / reset | Envoy not on the control plane, nothing on hostPort 80 | `kubectl -n envoy-gateway-system get pod -o wide`; EG controller logs |
| EG log: `spec.strategy.rollingUpdate: Forbidden` | switching a live Deployment to Recreate | RollingUpdate `maxSurge: 0, maxUnavailable: 1` |
| MetalLB IP silent, Service has the IP | no node allowed to announce (`Local` policy + excluded node) | `externalTrafficPolicy: Cluster`; `kubectl -n metallb-system logs ds/metallb-speaker` |
| HTTPRoute exists, 404 from Envoy | hostname mismatch or route not attached | `kubectl describe httproute`: `Accepted`, `ResolvedRefs` |
| Prometheus target `down` | wrong port name / path, NetworkPolicy | /targets page shows the error; check the Service port name |
| Argo CD app `Unknown`, "repository not accessible" | deploy key missing or revoked | `./lab gitops` |
| Argo CD keeps reverting your change | selfHeal: Git wins | change it in Git |
| gh says "credentials saved in plain text" | keyring locked or absent | 01-host.md; `gh auth logout`, unlock, log in again |
| Port 80 already used on Windows | IIS, Skype, another WSL distro | `netstat -ano | findstr :80` then the PID in Task Manager |

## Reset levels
1. One app: `kubectl rollout restart deploy/<name>`.
2. One component: `helm -n <ns> rollback <release>` or rerun `./lab up`.
3. Everything: `./lab down && ./lab up` (then `./lab gitops`). About 5 minutes; nothing in the cluster is precious.
4. WSL itself: `wsl --shutdown` from Windows.
