# Lesson 6: CI/CD (from your branch to the cluster)

> Every change takes the same road: a branch, a check on your PC, a check on GitHub (CI), a review, a merge.
> After the merge, Argo CD ships it (CD).

![A change goes from branch to ./lab check (red, fixed, green), the push hook, CI on GitHub, review, merge, and Argo CD](gifs/delivery.gif)

## The idea

Think of a newspaper.

- A journalist writes on their own draft, never straight on the printed page: that is a **branch**.
- A spell checker runs on the journalist's desk before anyone else reads the draft: that is `./lab check`
  on your PC.
- The outbox refuses to send a draft that fails the spell check: that is the **pre-push hook**. It runs
  `./lab check` again every time you `git push`, and stops the push if it fails.
- The newsroom has its own proofreader, who checks every draft that arrives, whoever sent it: that is **CI**.
  GitHub runs `./lab check` once more, on its own machines. Your desk can be skipped; the proofreader cannot.
- The draft goes to the editor's desk: that is a **pull request** (PR).
- The editor reads it, and the chief editor decides to print, but only with the proofreader's OK:
  **review** and **merge**.
- The press prints what was approved: that is **delivery** (CD). Here, Argo CD.

## Words

| Word | Plain meaning |
|---|---|
| branch | your own line of work, separate from `main` |
| commit | one saved change, with a message saying why |
| pull request (PR) | a request to merge your branch into `main`, with the diff for others to read |
| gate | a check that must pass before a change can move on |
| hook | a small script Git runs by itself at a given moment; `pre-push` runs just before a push |
| CI | continuous integration: a server re-tests every change, every time; here, GitHub Actions |
| workflow | a file in `.github/workflows/` telling GitHub what to run, and when |
| runner | the machine that runs a CI job; here, one of GitHub's, fresh for every run |
| ruleset | GitHub's rules for a branch; here, `main` only changes through a PR whose CI is green |
| CD | continuous delivery: what was merged is shipped automatically; here, by Argo CD |
| lint, schema check | reading files for mistakes without running them |

## In our lab

- The gate is `./lab check`. It reads the `lab` script for shell mistakes (shellcheck), checks the workflow
  rules, and checks every Kubernetes file against its official format (kubeconform). A typo like
  `replcas: 5` fails here, not in the cluster.
- The pre-push hook (`.githooks/pre-push`) runs `./lab check` before every push, and also refuses pushes to
  `main`. Git never switches a hook on by itself: run `git config core.hooksPath .githooks` once.
- CI: `.github/workflows/check.yml` runs `./lab check` on every PR, on GitHub's machines. It is free because the
  repo is public. Its result is a check called `passed`. When it is red, an issue opens on the PR; the next
  green run closes it.
- `main` is protected by a ruleset: no direct push, and a PR merges only when `passed` is green. A maintainer
  merges (in your own fork, that is you). After the merge, Argo CD (lesson 5) deploys whatever changed in `apps/`.

Deep dive: [handbook 6, CI and delivery](../handbook/06-ci.md).

## Try it

1. `./lab check`: it ends with a kubeconform summary showing `Invalid: 0, Errors: 0`.
2. Break it on purpose (do not commit this):

   ```bash
   sed -i 's/replicas: 5/replcas: 5/' apps/echo/echo.yaml
   ./lab check                        # fails: "replcas" is not allowed
   git checkout apps/echo/echo.yaml   # undo
   ```

3. See the hook guard the door (switch it on first, above): on a test branch, commit that same typo and `git push`. The push is
   refused with "./lab check failed". Undo the commit (`git reset --hard HEAD~1`) and delete the branch.
4. The whole road for real: a branch, a small change (a typo in a doc), `./lab check`, `git push`,
   `gh pr create --fill`, then `gh pr checks --watch` to watch CI. Merge once `passed` is green.

## When it breaks

- **The push is refused, "./lab check failed"**: the hook did its job. Run `./lab check`, read the error,
  fix it, push again.
- **CI is red, but `./lab check` is green on your PC**: something that exists only on your PC makes it pass,
  such as a file you never committed. CI starts from a clean copy of the commit. Open the run from the issue's
  link, or `gh run view --log-failed`.
- **The check passes, but Argo CD shows Degraded**: the check only reads files; it cannot know that an image
  tag does not exist or that the app crashes. Revert the commit (lesson 5).
- **kubeconform cannot download schemas**: it fetches them from the internet, so the check needs a
  connection.

## Check yourself

<details><summary>1. Why does the hook run <code>./lab check</code> again, if you already ran it?</summary>

Because people forget. The hook makes the check automatic: a push cannot leave your PC with a red check.
</details>

<details><summary>2. If the hook already checks every push, why also CI?</summary>

Because a hook lives on one PC: a fresh clone, another machine or `git push --no-verify` skips it. CI runs for
every pull request, from a clean copy, and `main`'s ruleset refuses the merge until it is green. Nobody can
skip it.
</details>

<details><summary>3. In this lab, which step actually deploys to the cluster?</summary>

Argo CD, after the merge, by syncing `main`. The checks only read files; they never deploy.
</details>

Next: [Lesson 7: Troubleshooting](07-troubleshooting.md)
