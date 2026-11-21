# Security

## What is in scope

devops-lab is one script (`lab`) and the Kubernetes manifests it applies, to build a practice platform on your
own PC. `./lab` runs with your rights: it calls docker, kind, kubectl, helm and gh; `./lab tools` installs two
pinned tools into `~/.local/bin` after checking their SHA-256; `./lab gitops` adds a read-only deploy key to the
GitHub repo the clone points at. The workflows in `.github/workflows/` run `./lab check` on GitHub's runners.

A security problem is anything that makes it do more than that, for example:
- running or downloading something that is not pinned and checked;
- leaking a secret: the Argo CD deploy key, the generated admin passwords, your gh token;
- a workflow that a pull request, from a fork or not, could use to run code with write access or secrets;
- a command in the docs that does harm when run as written, or changes state while it is presented as a read.

Known and accepted: the lab is for practice on one PC, and its port 80 listens on 127.0.0.1 only. Its web UIs
use plain HTTP and admin passwords generated in the cluster. `*.localtest.me` is a third-party public DNS name
that answers 127.0.0.1; to avoid depending on it, use the hosts-file line in the README. Pods have no
NetworkPolicy, and the demo app runs no commands. Do not expose the lab to a network.

## Supported versions

Only `main` is supported: a fix lands when it is merged.

## Reporting a problem

Please do not open a public issue. Report it privately through GitHub's
[private vulnerability reporting](https://github.com/makavli/devops-lab/security/advisories/new): what you found,
how to reproduce it, and what it could let someone do.
