# Contributing

Contributions should keep Agent workloads isolated, make runtime actions observable, validate user-controlled input, and avoid claiming unsupported capabilities.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py --port 5000
```

## Tests and Validation

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
docker compose config
docker compose -f docker-compose.dev.yml config
```

Tests must not require real Docker, paid model credentials, or external network services. Mock the runtime adapter for lifecycle tests. Add negative tests for schema, ownership, permissions, path handling, and state transitions when extending those areas.

## Design Requirements

- Keep Flask route handlers thin and put Docker operations in `services/container_runtime.py`.
- Use `/api/v1` for new APIs and return structured JSON errors with appropriate status codes.
- Scope persisted data and logs to the authenticated owner.
- Do not pass host paths, secrets, or the Docker socket to Agent containers.
- Preserve non-root execution, resource bounds, read-only roots, and no-network defaults unless an explicit reviewed requirement changes them.
- Update documentation when behavior changes. Never commit `.env`, credentials, tokens, or generated database contents.
- Preserve the existing MIT license and upstream attribution.