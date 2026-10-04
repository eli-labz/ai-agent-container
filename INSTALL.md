# Installation

## Requirements

- Python 3.11+ for a local install, or Docker Compose v2 for a containerized deployment.
- A reachable Docker Engine for Agent Runtime lifecycle operations.
- Runtime images preloaded into that Docker Engine.

The Control Plane does not require AI provider credentials to boot.

## Local Install

```bash
git clone https://github.com/eli-labz/ai-agent-container.git
cd ai-agent-container
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py --port 5000
```

The default metadata database is SQLite under `data/`. Existing installations keep using the historic `data/flowcase.db` path so an upgrade does not silently strand local records. Set `AI_AGENT_CONTAINER_DATABASE_URL` to select another SQLAlchemy-supported database URL.

## Docker Compose

Review the Docker socket mount in `docker-compose.yml` before starting. The web service needs access to the host Docker daemon to create runtimes. This grants substantial host control to the Control Plane; never mount the socket into an Agent container or expose this service to untrusted users.

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f web
```

The default Compose file includes the existing Traefik and Authentik configuration. For local development, use `docker compose -f docker-compose.dev.yml up --build` and inspect the published port with `docker compose ps`.

Validate before deployment:

```bash
docker compose config
docker compose -f docker-compose.dev.yml config
docker compose -f docker-compose-traefik.yml config
docker compose -f docker-compose-authentik.yml config
```

`install.sh` and `install.ps1` are retained for the existing Compose deployment. Review generated settings and the socket mount before using them. Traefik and Authentik remain optional integrations; third-party service names are unchanged.

## Data and Upgrade Notes

Back up `data/`, `.env`, and Docker volumes before upgrades. The legacy desktop-container subsystem and its database remain available for compatibility. Agent metadata is added with SQLAlchemy `create_all`; existing tables are not migrated automatically. Production deployments need explicit schema migrations before relying on upgrades.