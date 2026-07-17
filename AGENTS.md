# Repository working agreement

These instructions apply to all work in this repository.

## Scope

- Keep source code, generated project artifacts, caches, and development changes inside this repository.
- Do not modify host system files or global configuration as part of normal development.
- Never commit `.env`, credentials, tokens, private keys, or production data.

## Validation

- Use the Docker Linux Engine installed on the active development host as the primary integration environment.
- After moving the repository to another host, rebuild dependencies and images from lockfiles; do not reuse virtual environments, `node_modules`, or Docker volumes from the previous host.
- Run the checks relevant to every change. For cross-cutting or infrastructure changes, run the complete gate with `./scripts/verify-p0.ps1` and the Docker Compose smoke tests.
- Use the isolated Compose project name `hermes-subscription-manager-local` for automated local validation.
- Do not claim GitHub Actions passed unless an actual GitHub Actions run is available.

## Git workflow

- Treat each coherent, validated change as one Git commit.
- After completing and validating a requested change, stage only the intended repository files and create a descriptive commit automatically.
- Do not amend, squash, rebase, force-push, or delete user commits unless explicitly requested.
- Do not push to a remote unless explicitly requested.
- If validation fails, do not commit the failing change; diagnose and fix it first, or report the blocker.
