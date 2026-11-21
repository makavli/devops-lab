# Lesson 6: Delivery (from your branch to the cluster)

> Every change takes the same road: a branch, a check on your PC, a review, a merge. After the merge,
> Argo CD ships it. Every test runs on your PC; there is no CI server.

![A change goes from branch to ./lab check (red, fixed, green), push with the hook checking again, review, merge, and Argo CD](gifs/delivery.gif)

## The idea

Think of a newspaper.

- A journalist writes on their own draft, never straight on the printed page: that is a **branch**.
- A spell checker runs on the journalist's desk before anyone else reads the draft: that is `./lab check`
  on your PC.
- The outbox refuses to send a draft that fails the spell check: that is the **pre-push hook**. It runs
  `./lab check` again every time you `git push`, and stops the push if it fails.
- The draft goes to the editor's desk: that is a **pull request** (PR).
- The editor reads it, and the chief editor decides to print: **review** and **merge**.
- The press prints what was approved: that is **delivery**. Here, Argo CD.

Many teams also run the checks again on a server after every push. That is called **CI** (continuous
integration). This lab does not: it is a private repo, so GitHub only stores the code. Every test runs on
your PC, and must pass there before anything leaves it.

## Words

| Word | Plain meaning |
|---|---|
| branch | your own line of work, separate from `main` |
| commit | one saved change, with a message saying why |
| pull request (PR) | a request to merge your branch into `main`, with the diff for others to read |
| gate | a check that must pass before a change can move on |
| hook | a small script Git runs by itself at a given moment; `pre-push` runs just before a push |
| CI | continuous integration: a server re-tests every change; not used here |
| CD | continuous delivery: what was merged is shipped automatically; here, by Argo CD |
| lint, schema check | reading files for mistakes without running them |

## In our lab

- The gate is `./lab check`. It reads the `lab` script for shell mistakes (shellcheck), and checks every
  Kubernetes file against its official format (kubeconform). A typo like `replcas: 5` fails here, not in
  the cluster.
- The pre-push hook (`.git/hooks/pre-push`, on this PC only) runs `./lab check` before every push, and also
  refuses pushes to `main`. Hooks are not part of the repo: a fresh clone has none until you add it.
- GitHub Actions is turned off on the repo. No workflow runs, and nothing costs minutes.
- Only the owner merges. After the merge, Argo CD (lesson 5) deploys whatever changed in `apps/`.

Deep dive: [handbook 6, delivery](../handbook/06-ci.md).

## Try it

1. `./lab check`: it ends with a kubeconform summary showing `Invalid: 0, Errors: 0`.
2. Break it on purpose (do not commit this):

   ```bash
   sed -i 's/replicas: 5/replcas: 5/' apps/echo/echo.yaml
   ./lab check                        # fails: "replcas" is not allowed
   git checkout apps/echo/echo.yaml   # undo
   ```

3. See the hook guard the door: on a test branch, commit that same typo and `git push`. The push is
   refused with "./lab check failed". Undo the commit (`git reset --hard HEAD~1`) and delete the branch.
4. The whole road for real: a branch, a small change (a typo in a doc), `./lab check`, `git push`,
   `gh pr create --fill`, then merge it in the browser.

## When it breaks

- **The push is refused, "./lab check failed"**: the hook did its job. Run `./lab check`, read the error,
  fix it, push again. Never skip the hook with `git push --no-verify`: nothing else would catch the mistake.
- **The check passes, but Argo CD shows Degraded**: the check only reads files; it cannot know that an image
  tag does not exist or that the app crashes. Revert the commit (lesson 5).
- **kubeconform cannot download schemas**: it fetches them from the internet, so the check needs a
  connection.

## Check yourself

<details><summary>1. Why does the hook run <code>./lab check</code> again, if you already ran it?</summary>

Because people forget. The hook makes the check automatic: a push cannot leave your PC with a red check.
</details>

<details><summary>2. What does a CI server add that a local hook does not?</summary>

A place nobody can skip. A hook lives on one PC: a fresh clone, another machine or `--no-verify` bypasses it.
In a team that matters; in this one-person private lab, the hook plus your review is enough, and it costs
nothing.
</details>

<details><summary>3. In this lab, which step actually deploys to the cluster?</summary>

Argo CD, after the merge, by syncing `main`. The checks only read files; they never deploy.
</details>

Next: [Lesson 7: Troubleshooting](07-troubleshooting.md)
