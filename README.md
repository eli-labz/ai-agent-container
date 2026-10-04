# AI Agent Container

AI Agent Container is an open-source, container-native control plane for running AI agents inside isolated, observable workspaces with explicit runtime constraints.

Each Agent Definition describes a runtime image, a bounded `/workspace`, resource limits, network access, and approval metadata. Operators can create an Agent, launch and control its container, queue Tasks, inspect Events, and read runtime logs through the web console or `/api/v1`.

> **Project status:** early development. The Agent API and container lifecycle path are implemented, but queued tasks do not yet have a bundled execution worker. Provider credentials, approvals, artifacts, and policy enforcement are not complete. Do not treat this release as production-ready.

## Current Capabilities

- Authenticated Agent console at `/agents` alongside the retained legacy desktop-container dashboard at `/dashboard`.
- Versioned YAML/JSON Agent Definitions with validation for names, images, non-root user IDs, resource bounds, workspaces, network access, and approval modes.
- Persistent Agent, Task, and Event metadata in the existing SQLAlchemy database.
- Docker runtime create, start, stop, restart, pause, resume, inspect, and logs operations.
- Runtime defaults: non-root UID, dropped Linux capabilities, `no-new-privileges`, read-only root filesystem, isolated network by default, PID/CPU/memory limits, and an application-managed workspace volume.
- Owner-scoped API records and structured JSON errors.
- Optional Traefik and Authentik integration retained from the existing deployment.

## Architecture

The Flask application is the Control Plane. It owns the web console, authenticated API, SQLite metadata by default, and a Docker SDK runtime adapter. Agent containers do not receive the Docker socket. The legacy desktop-container routes remain available for existing deployments; they are not the Agent execution worker. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Security Model

Agent containers run with a non-root numeric UID, all Linux capabilities dropped, `no-new-privileges`, a read-only root filesystem, bounded CPU/memory/PIDs, and an application-managed workspace volume. Network access defaults to disabled; enabling bridge networking permits general Docker-network egress and is not an outbound allowlist. Runtime images must support the configured UID and a writable `/workspace` mount.

The Control Plane requires Docker daemon access to manage containers. A mounted Docker socket grants powerful host control to the Control Plane and must never be mounted into Agent containers. Limit access to the web application to trusted operators. The current authorization model scopes records to the signed-in user; administrator/operator/viewer roles and approval enforcement are not implemented yet.

## Prerequisites

- Python 3.11 or newer and the packages in `requirements.txt`.
- Docker Engine accessible to the user running the Control Plane.
- A runtime image already available in the Docker daemon. Image pulling and provider credentials are not managed by the Agent API yet.

## Quick Start

```bash
git clone https://github.com/eli-labz/ai-agent-container.git
cd ai-agent-container
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py --port 5000
```

Open `http://localhost:5000/agents`. On a fresh database, the retained bootstrap creates an `admin` account and prints its generated password to startup logs. Change it immediately. The Control Plane boots without model-provider keys.

For Docker Compose and proxy options, see [INSTALL.md](INSTALL.md) and [SETUP.md](SETUP.md).

## Example Agent

```yaml
apiVersion: ai-agent-container/v1
kind: Agent
metadata:
  name: research-agent
  description: Research and analysis worker
spec:
  runtime:
    image: python:3.12-slim
    command: [python, -c, "import time; time.sleep(10**9)"]
  workspace:
    persistent: true
    path: /workspace
  resources:
    cpu: "1"
    memory: 1Gi
    pids: 256
  capabilities:
    network:
      enabled: false
  tools: []
  approvalPolicy:
    mode: risk-based
```

More starter definitions are in [examples/agents](examples/agents).

## API

The API uses the existing signed-in web session. Health and readiness are public; Agent and Task records are owner-scoped.

```bash
curl -b cookies.txt http://localhost:5000/api/v1/agents
curl -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"definition":"apiVersion: ai-agent-container/v1\nkind: Agent\nmetadata:\n  name: example\nspec:\n  runtime:\n    image: python:3.12-slim\n"}' \
  http://localhost:5000/api/v1/agents
```

See [QUICKSTART.md](QUICKSTART.md) for login and lifecycle requests. API endpoints return structured JSON errors.

## Development and Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
docker compose config
```

Tests use an in-memory SQLite database and mocked Docker objects; they do not require Docker or paid model-provider credentials. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- Add a durable task worker and a documented Agent task protocol.
- Implement Approval, Artifact, Run, Provider, Credential, Tool, and Policy services with authorization and audit coverage.
- Add migrations and production database configuration for Agent metadata.
- Add network policy controls and image provenance enforcement.
- Replace legacy desktop-container UI and identifiers only after a supported migration path exists.

## License and Attribution

Distributed under the MIT License; see [LICENSE](LICENSE). The existing license attribution is preserved. This repository is maintained at [eli-labz/ai-agent-container](https://github.com/eli-labz/ai-agent-container). Intentional compatibility references are catalogued in [MIGRATIONS.md](MIGRATIONS.md).