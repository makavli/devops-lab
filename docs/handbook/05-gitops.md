# 5. GitOps: Argo CD

## The model
Git holds the desired state; Argo CD continuously compares it with the cluster and converges.
Nobody runs `kubectl apply` against `apps/` once GitOps is on: you change Git, through a PR.

```
PR merged to main ─► Argo CD repo-server renders apps/ ─► application-controller diffs vs live
                    ─► sync (apply) ─► health assessment (Healthy / Progressing / Degraded)
```

## Here
| Piece | Where |
|---|---|
| Argo CD v3.6 (chart pinned in `./lab`) | namespace `argocd`, values `platform/argocd/values.yaml` |
| UI | http://argocd.localtest.me, `admin` / `./lab passwords` |
| Root Application `apps` | `gitops/root.yaml`: syncs `apps/` (recursive) from `main` |
| Repo access | read-only deploy key in Secret `repo-devops-lab`, created by `./lab gitops` |

Sync policy: `automated` with `prune` (files deleted in Git are deleted in the cluster) and `selfHeal`
(manual edits are reverted within seconds). The root app has the resources finalizer: deleting it deletes
everything it deployed.

Not GitOps-managed yet: the platform itself (`./lab up` installs it with Helm). Moving MetalLB, Envoy
Gateway, monitoring and Argo CD under Argo CD (Applications with `helm` sources) is a later exercise;
Argo CD managing itself is the usual end state.

## Turn it on
Needs: gh logged in (keyring), the repo pushed to GitHub.
```bash
./lab gitops
```
It generates a fresh ed25519 key in a temp dir, deletes any old `argocd-lab` deploy key on GitHub, uploads
the new public key (read-only), stores the private key only in the cluster Secret, deletes the temp dir,
and applies the root app. Rerun it any time to rotate. After `./lab down && ./lab up`, run it again.

Security notes: the key sits base64-encoded in etcd (no encryption at rest in kind). In prod: etcd
encryption with KMS, and secrets from a manager (External Secrets Operator, Sealed Secrets), never in Git.

## Daily use
```bash
kubectl -n argocd get applications
kubectl -n argocd get application apps -o jsonpath='{.status.sync.status} {.status.health.status}{"\n"}'
```
In the UI: the app tree (Deployment → ReplicaSet → Pods) with health per object, live diff, history and
rollback, pod logs, and resource actions (restart, delete).

Optional CLI: `curl -sSLo ~/.local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64 && chmod +x ~/.local/bin/argocd`,
then `argocd login argocd.localtest.me --plaintext --grpc-web`.

First login hygiene: change the admin password (User Info → Update password), then
`kubectl -n argocd delete secret argocd-initial-admin-secret` (after that, `./lab passwords` cannot show it).

## Exercises
1. **Drift**: `kubectl scale deploy/echo --replicas=1`. Watch selfHeal put it back to 3 in the UI.
2. **Change through Git**: on a branch set `replicas: 5`, PR, merge; watch OutOfSync → Syncing → Synced.
3. **Prune**: add a ConfigMap file under `apps/echo/`, merge, then delete the file and merge. It disappears.
4. **Bad deploy**: set an image tag that does not exist. Health goes Degraded (ImagePullBackOff).
   Roll back by reverting the commit, not by clicking: Git stays the truth.
5. **Sync waves**: annotate a Job `argocd.argoproj.io/sync-wave: "-1"` to run it before the Deployment.
6. Split apps into one Application per directory with an **ApplicationSet** (git directory generator).
