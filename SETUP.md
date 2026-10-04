# Setup and Configuration

## Environment

Copy `.env.example` to `.env`. The Control Plane uses SQLite by default and generates a local Flask session secret if `SECRET_KEY` is unset.

| Variable | Purpose | Default |
| --- | --- | --- |
| `AI_AGENT_CONTAINER_ENV` | Environment label | `development` |
| `AI_AGENT_CONTAINER_HOST` | Local Gunicorn bind host | `0.0.0.0` |
| `AI_AGENT_CONTAINER_PORT` | Local server port | `5000` |
| `AI_AGENT_CONTAINER_DATABASE_URL` | SQLAlchemy metadata-store URL | historic SQLite path |
| `SECRET_KEY` | Flask session signing key | generated in `data/secret_key` |
| `DOCKER_HOST` | Docker SDK daemon address | Docker SDK default |
| `DOMAIN` | Public host used by proxy configuration | `localhost` |
| `LOG_LEVEL` | Desired log verbosity | `INFO` |

`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GOOGLE_API_KEY` may be set for future integrations, but the current platform does not load or distribute them to Agent containers. Never put secret values in an Agent Definition.

## Authentication

The existing local login and optional Authentik header integration are retained. New API routes use the signed-in session, return JSON `401` responses, and scope records to the authenticated user. This is not a complete role-based authorization system: administrator, operator, and viewer roles are not yet defined for Agent operations.

On a fresh database, the retained bootstrap creates `admin` and `user` accounts and prints generated passwords to startup logs. Restrict log access and immediately replace those credentials. Authentik headers must only be trusted when a correctly configured reverse proxy strips client-supplied copies and injects authenticated values.

## Agent Runtime

Agent images must be present on the Docker host before launch and provide a long-running foreground process (through their image entrypoint or the validated argv-list `spec.runtime.command`). Each runtime receives a named `/workspace` volume and is configured with:

- Numeric non-root UID/GID (default `10000:10000`). Images must prepare that identity and make `/workspace` writable by it.
- A read-only root filesystem, `no-new-privileges`, dropped capabilities, and a small `/tmp` tmpfs.
- CPU quota, memory limit, and PID limit from the validated definition.
- No network by default. `network.enabled: true` attaches to Docker bridge networking and permits general egress; it is not an allowlist.

The starter images run an idle bounded process for lifecycle demonstrations. They do not execute queued Tasks.

The Control Plane Docker socket is a privileged management channel. Agent workloads are not given access to it. Avoid host bind mounts and never run Agent containers with `privileged: true`.

## API and Health

API base path: `/api/v1`. Public probes are `GET /api/v1/health` and `GET /api/v1/readiness`; other API routes require an authenticated session. Health reports process status; readiness checks the metadata database, not Docker or a model provider.

## Known Gaps

Task records are durable but remain queued because there is no worker or execution protocol. Provider and Credential objects, Approval enforcement, artifact export, tool dispatch, network egress rules, production migrations, and role-based authorization are not implemented. Do not enable autonomous external actions based on approval metadata alone.