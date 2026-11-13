# 1. Host: WSL2, Docker Engine, credentials

## What runs where
- **WSL2** is a lightweight Hyper-V VM with a real Linux kernel (6.6, `microsoft-standard-WSL2`).
  systemd is PID 1 (`/etc/wsl.conf` → `[boot] systemd=true`), so services behave as on a server.
- **Docker Engine** (not Desktop) runs on that systemd: one network stack, no license question,
  the same as a Linux build agent.
- **Ports**: anything that listens on `0.0.0.0` or `localhost` inside WSL is forwarded to Windows `localhost`
  (the `wslrelay` process). Subnets inside WSL (Docker bridges, 172.18.x) are not routed to Windows.

## Install recap (already done on this PC)
| Piece | How | Note |
|---|---|---|
| WSL service | `Set-Service WSLService -StartupType Automatic` (admin) | it had been *Disabled*: error `Wsl/0x80070422` |
| Ubuntu 24.04 | `wsl --install -d Ubuntu-24.04` | 24.04 over 26.04: tooling and guides target it |
| Docker | apt repo `download.docker.com`, deb822 source | Ubuntu's `docker.io` lags and lacks buildx/compose |
| docker group | `usermod -aG docker $USER`, then a new login | root-equivalent; prod uses rootless or Podman |
| kubectl, kind, helm | static binaries in `/usr/local/bin` | `./lab tools` adds kubeconform and k9s in `~/.local/bin` |
| jq, shellcheck | `sudo apt-get install -y jq shellcheck` | used in the handbooks and by `./lab check` |
| inotify | `/etc/sysctl.d/99-kind.conf` (512 instances, 524288 watches) | multi-node kind fails with "too many open files" otherwise |

deb822 gotchas we hit: `Types: deb` (not `dev`), and **no blank line inside a stanza**: a blank line
starts a new stanza, and apt reports "Malformed stanza 2".

## Resources
WSL gets half the RAM by default (15 GiB here). The full platform uses ~4-5 GiB.
Cap or raise it in `C:\Users\<you>\.wslconfig`:
```ini
[wsl2]
memory=20GB
processors=8
```
Then `wsl --shutdown` from Windows.

## Credentials: nothing in plain text
Rule: no token or private key at rest unencrypted on this box.

| Secret | Where it lives | Protection |
|---|---|---|
| gh token | GNOME keyring (Secret Service over D-Bus) | encrypted with the keyring password, unlocked once per WSL boot |
| your SSH key | `~/.ssh/id_ed25519` | **passphrase** + `ssh-agent` holding it for the session |
| Argo CD deploy key | Kubernetes Secret only (`./lab gitops`) | read-only, rotated on every run, never written to disk |
| runner token | single-use, 1 h | consumed by `./lab runner` |

### Keyring setup
```bash
sudo apt-get install -y gnome-keyring libsecret-tools dbus-user-session wslu
echo 'export BROWSER=wslview' >> ~/.bashrc     # gh/xdg-open open the Windows browser
```
Unlock function in `~/.bashrc` (runs in interactive shells only, prompts once per boot):
```bash
keyring_unlock() {
  [ "$(busctl --user get-property org.freedesktop.secrets /org/freedesktop/secrets/collection/login \
        org.freedesktop.Secret.Collection Locked 2>/dev/null)" = "b false" ] && return
  local p=; while [ -z "$p" ]; do read -rsp "Keyring password: " p; echo; done
  printf '%s' "$p" | gnome-keyring-daemon --replace --unlock --components=secrets >/dev/null
  unset p
}
[ -t 0 ] && keyring_unlock
```
Lesson: with an **empty** password, `--unlock` silently creates nothing (no `login` collection, no error),
and gh falls back to plain text. Hence the loop.

Check, then log in:
```bash
busctl --user get-property org.freedesktop.secrets /org/freedesktop/secrets/collection/login org.freedesktop.Secret.Collection Locked   # b false
gh auth login -h github.com --git-protocol ssh --web
gh auth status                          # must say (keyring)
cat ~/.config/gh/hosts.yml              # must hold no oauth_token
```
Limit: once unlocked, any process running as you can read the secrets over D-Bus. A keyring protects data
at rest (a stolen disk, a backup), not against malware running as you.

### SSH key with passphrase + agent
```bash
ssh-keygen -t ed25519 -C "devops-lab WSL" -f ~/.ssh/id_ed25519     # set a passphrase
gh ssh-key add ~/.ssh/id_ed25519.pub --title "WSL $(hostname)"
sudo apt-get install -y keychain
echo 'eval "$(keychain --eval --quiet id_ed25519)"' >> ~/.bashrc   # one passphrase prompt per boot
ssh -T git@github.com
```

### Git identity
Use GitHub's noreply address so your real email never enters history:
```bash
git config --global user.name makavli
git config --global user.email "$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
```

### If a token leaks
`gh auth logout` only deletes the local copy. Revoke on the server:
github.com → Settings → Applications → Authorized OAuth Apps → GitHub CLI → Revoke.
