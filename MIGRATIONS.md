# Compatibility and Migration Notes

AI Agent Container retains the existing desktop-container subsystem while Agent Runtime APIs are introduced. These occurrences are intentional compatibility references, not current product branding:

- `LICENSE` retains the original copyright and MIT license attribution.
- `config/config.py`, `utils/setup.py`, and the database filename retain legacy storage/bootstrap names so upgrades continue using existing user records.
- `models/droplet.py` retains the existing remote-server password column; it is plaintext at rest pending a migration and managed encryption-key design.
- Existing `routes/`, `utils/docker.py`, and `docker-compose*.yml` retain Flowcase-derived container, network, volume, and Authentik identifiers consumed by existing installations.
- `web.Dockerfile` retains `/flowcase` as its working directory because legacy Nginx configuration and mounted data paths depend on it; `static/js/dashboard/admin.js` retains the legacy default-network identifier in its compatibility dashboard.
- Existing Guacamole/desktop image names and Authentik integration labels identify third-party or legacy components, not the Agent Runtime image.
- `routes/auth.py` and `routes/admin.py` accept legacy `FLOWCASE_*` authentication/registry settings for compatibility; new application settings use the `AI_AGENT_CONTAINER_` prefix.

Do not rename these identifiers in place until the application supports data/container discovery under both old and new names and includes a tested migration. New code, docs, APIs, and images should use `AI Agent Container` and `ai-agent-container`.