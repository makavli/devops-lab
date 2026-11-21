# 2. Cluster: kind

## Why kind
Each node is a Docker container running systemd, containerd and kubelet, bootstrapped by **kubeadm**:
a real control plane (etcd, kube-apiserver, scheduler, controller-manager as static pods in
`/etc/kubernetes/manifests`). k3d is lighter but swaps etcd for SQLite and bundles Traefik and a service LB,
hiding what we want to learn. Minikube is single-node by default.

## Layout (`cluster/kind.yaml`)
| Node | Role | Special |
|---|---|---|
| lab-control-plane | control plane, tainted `NoSchedule` | label `ingress-ready=true`; port 80 published on 127.0.0.1 |
| lab-worker, lab-worker2 | workloads | |

The Envoy proxy tolerates the taint and is pinned to the control plane, the only node with published ports.

## Daily commands
```bash
./lab up / ./lab down          # build or destroy everything
kubectl get nodes -o wide
docker exec -it lab-control-plane bash          # "ssh" into a node
docker exec lab-control-plane crictl ps         # containers as the kubelet sees them
docker exec lab-control-plane ls /etc/kubernetes/manifests   # static pods
k9s                                             # terminal UI (./lab tools installs it)
```

## Look inside
- **etcd**: `kubectl -n kube-system exec etcd-lab-control-plane -- etcdctl --cacert /etc/kubernetes/pki/etcd/ca.crt --cert /etc/kubernetes/pki/etcd/server.crt --key /etc/kubernetes/pki/etcd/server.key get /registry/deployments/default/echo --print-value-only | head -c 300`
  shows how objects are stored. Note Secrets are only base64 in etcd here: prod enables encryption at rest (KMS).
- **Certificates**: `docker exec lab-control-plane kubeadm certs check-expiration`.
- **kubelet logs**: `docker exec lab-control-plane journalctl -u kubelet --since -10m`.

## Exercises
1. Stop a worker: `docker stop lab-worker`. Watch `kubectl get nodes -w` go NotReady after ~40 s and pods
   get evicted after the 5 min `tolerationSeconds` of `node.kubernetes.io/unreachable`. `docker start` it.
2. Stop the scheduler: move its static pod manifest out, and the kubelet removes the pod. A new pod stays
   Pending with no events, because nothing is there to place it.
   ```bash
   docker exec lab-control-plane mv /etc/kubernetes/manifests/kube-scheduler.yaml /root/
   kubectl run probe --image=registry.k8s.io/pause:3.10; kubectl get pod probe        # Pending
   docker exec lab-control-plane mv /root/kube-scheduler.yaml /etc/kubernetes/manifests/   # undo: probe runs
   kubectl delete pod probe
   ```
3. Upgrade practice: change the pinned node `image:` lines in `cluster/kind.yaml` (tags and digests are in
   kind's release notes), `./lab down && ./lab up && ./lab gitops`, and check what broke.
4. Re-enable control-plane metrics: add `kubeadmConfigPatches` binding scheduler/controller-manager/etcd
   metrics to `0.0.0.0`, then turn them back on in `platform/monitoring/values.yaml`.

Exercises 3 and 4 rebuild the cluster, which nothing in it survives. Undo both:
`git checkout cluster/kind.yaml platform/monitoring/values.yaml && ./lab down && ./lab up && ./lab gitops`.
