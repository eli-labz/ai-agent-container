# Quick Start

This starts the AI Agent Container Control Plane locally. Docker must be reachable, but provider credentials are optional and the current task queue does not call a model.

## Start

```bash
git clone https://github.com/eli-labz/ai-agent-container.git
cd ai-agent-container
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py --port 5000
```

Open `http://localhost:5000/agents`. A fresh database creates an `admin` account and prints its generated password to server logs. Change it immediately and do not expose first-run setup to an untrusted network.

## Define an Agent

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

Definitions are validated before storage. Approval mode is metadata only in this release; it does not gate actions.

## API Workflow

Sign in at `/` to establish a session, then reuse the cookie with `curl`:

```bash
curl -c cookies.txt -b cookies.txt -d 'username=admin&password=YOUR_PASSWORD' \
  -X POST http://localhost:5000/login
curl -b cookies.txt http://localhost:5000/api/v1/agents
curl -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"definition":"apiVersion: ai-agent-container/v1\nkind: Agent\nmetadata:\n  name: research-agent\nspec:\n  runtime:\n    image: python:3.12-slim\n"}' \
  http://localhost:5000/api/v1/agents
```

Use the returned Agent `id` for lifecycle operations:

```bash
curl -b cookies.txt -X POST http://localhost:5000/api/v1/agents/AGENT_ID/start
curl -b cookies.txt http://localhost:5000/api/v1/agents/AGENT_ID/runtime
curl -b cookies.txt http://localhost:5000/api/v1/agents/AGENT_ID/logs
curl -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"agent_id":"AGENT_ID","title":"Review files","instructions":"Inspect the workspace"}' \
  http://localhost:5000/api/v1/tasks
curl -b cookies.txt -X POST http://localhost:5000/api/v1/agents/AGENT_ID/stop
```

Tasks are stored as `queued` and appear in Tasks and Events. No worker executes task instructions yet. Runtime images must already exist in Docker; provider credentials, task dispatch, and artifact export are not implemented.

Stop the server with `Ctrl+C`. Stop Agent containers from the console or API before shutting down Docker.