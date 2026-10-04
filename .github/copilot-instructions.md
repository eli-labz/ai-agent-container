# AI Agent Container Coding Guidance

AI Agent Container is an early-stage Flask control plane for defining Agents, managing Docker Agent Runtimes, persisting Tasks and Events, and observing lifecycle/logs. Task execution is not implemented; do not describe queued Tasks as running work.

## Architecture and Directories

- `run.py`: Flask/Gunicorn bootstrap.
- `routes/`: authenticated Flask routes; new API endpoints use `/api/v1`.
- `models/`: SQLAlchemy domain records.
- `services/agent_definition.py`: versioned YAML/JSON definition validation.
- `services/container_runtime.py`: the only new Agent Docker adapter.
- `templates/`, `static/`: web console and existing UI assets.
- `examples/agents/`: valid human-authored definitions.
- `tests/`: unittest suite using in-memory SQLite and mocked Docker behavior.

## Working Agreements

- Install: `pip install -r requirements.txt`; run: `python run.py --port 5000`.
- Test: `python -m unittest discover -s tests -v`; syntax: `python -m compileall -q .`.
- Compose validation: `docker compose config` and validate each auxiliary Compose file independently.
- Keep routes thin, errors structured, records owner-scoped, and configuration explicitly validated.
- Never commit secrets. Provider keys must not enter definitions, images, logs, or event metadata.
- Preserve container isolation: no privileged containers, Docker socket mounts, arbitrary host bind mounts, or unbounded resources for Agent workloads. Network remains disabled by default.
- The web Control Plane's Docker socket is privileged host access; never forward it into Agent containers.
- Add tests for success and invalid/unauthorized cases. Mock Docker; do not require paid providers.
- Update `README.md`, `SETUP.md`, `SECURITY.md`, and `ARCHITECTURE.md` when behavior or operational requirements change.
- Preserve the MIT license and its existing attribution; document intentional legacy branding references in `MIGRATIONS.md`.