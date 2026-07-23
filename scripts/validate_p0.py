from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise AssertionError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return content


def validate_compose() -> None:
    compose = load_yaml(ROOT / "compose.yml")
    services = compose.get("services")
    assert isinstance(services, dict), "compose.yml must define services"
    assert set(services) == {"db", "migrate", "backend", "scheduler", "frontend"}

    migrate = services["migrate"]
    backend = services["backend"]
    scheduler = services["scheduler"]
    frontend = services["frontend"]
    assert migrate["command"] == ["alembic", "upgrade", "head"]
    assert migrate["depends_on"]["db"]["condition"] == "service_healthy"
    assert backend["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert scheduler["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert backend["build"]["context"] == scheduler["build"]["context"] == "./backend"
    assert scheduler["command"] == ["python", "-m", "app.scheduler"]
    assert frontend["depends_on"]["backend"]["condition"] == "service_healthy"
    assert compose.get("volumes", {}).get("postgres-data") is None


def validate_ci() -> None:
    workflow = load_yaml(ROOT / ".github" / "workflows" / "ci.yml")
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    required_jobs = {
        "backend",
        "frontend",
        "compose",
        "e2e",
        "backup-restore",
        "performance",
    }
    assert required_jobs <= set(jobs), f"CI is missing jobs: {required_jobs - set(jobs)}"
    backend_steps = "\n".join(str(step.get("run", "")) for step in jobs["backend"]["steps"])
    frontend_steps = "\n".join(str(step.get("run", "")) for step in jobs["frontend"]["steps"])
    compose_steps = "\n".join(str(step.get("run", "")) for step in jobs["compose"]["steps"])
    e2e_steps = "\n".join(str(step.get("run", "")) for step in jobs["e2e"]["steps"])
    backup_steps = "\n".join(str(step.get("run", "")) for step in jobs["backup-restore"]["steps"])
    performance_steps = "\n".join(str(step.get("run", "")) for step in jobs["performance"]["steps"])
    for command in ("ruff check", "ruff format --check", "mypy", "pytest", "alembic upgrade"):
        assert command in backend_steps, f"backend CI is missing {command}"
    for command in (
        "npm ci",
        "npm audit --audit-level=high",
        "npm run lint",
        "npm run typecheck",
        "npm test",
        "npm run build",
    ):
        assert command in frontend_steps, f"frontend CI is missing {command}"
    assert "docker compose config --quiet" in compose_steps
    assert "./scripts/verify-e2e.ps1" in e2e_steps
    assert "./scripts/verify-backup-restore.ps1" in backup_steps
    assert "./scripts/verify-performance.ps1" in performance_steps


def validate_artifacts() -> None:
    required = (
        "README.md",
        ".env.example",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "backend/requirements.lock",
        "backend/Dockerfile",
        "backend/logging.json",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/Dockerfile",
        "docs/Hermes_Subscription_Manager_Development_Spec.md",
        "docs/Hermes_Subscription_Manager_Implementation_Plan.md",
    )
    for relative in required:
        path = ROOT / relative
        assert path.is_file() and path.stat().st_size > 0, f"missing or empty: {relative}"

    create_all_hits = []
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        if "create_all" in path.read_text(encoding="utf-8"):
            create_all_hits.append(str(path.relative_to(ROOT)))
    assert not create_all_hits, f"business schema must not auto-create: {create_all_hits}"

    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes" in dockerfile
    assert "--log-config" in dockerfile


def main() -> None:
    validate_compose()
    validate_ci()
    validate_artifacts()
    print("P0 static configuration validation passed.")


if __name__ == "__main__":
    main()
