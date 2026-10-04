# Security Policy

AI Agent Container is under active development and is not currently a production-ready security boundary for untrusted workloads.

## Reporting a Vulnerability

Please report vulnerabilities privately through [GitHub Security Advisories](https://github.com/eli-labz/ai-agent-container/security/advisories/new). Include the affected version, deployment details, impact, and reproduction steps. Do not include live credentials or customer data.

## Deployment Guidance

- Restrict Control Plane access to trusted, authenticated operators.
- Treat Docker daemon access and a mounted Docker socket as host-level privilege.
- Never mount the Docker socket, arbitrary host paths, or provider credentials into Agent workloads.
- Use trusted, pinned runtime images and verify image provenance before launching them.
- Keep Agent networking disabled unless a specific task requires it. Bridge access currently has no outbound allowlist.
- Back up and protect `data/`, `.env`, and Docker volumes. Change first-run account credentials immediately.
- Do not rely on `approvalPolicy` as an enforcement mechanism in this release.
- The retained desktop-container subsystem stores remote server passwords in its legacy database column without encryption at rest. Restrict and encrypt the database volume at the host/storage layer; do not add new credential features to that subsystem before a key-managed migration is available.
- The default Compose stack mounts the Docker socket into the Control Plane and Traefik; the included Authentik worker also mounts it for its optional Docker outpost integration. These are privileged third-party/control-plane integrations, not Agent workload permissions.
- The current web image runs as root to retain Docker socket compatibility. A compromised Control Plane can therefore exercise host-level Docker authority; treat this deployment as a trusted administrative service, not a sandbox for untrusted users. The Authentik worker also runs as root in the retained compose file for its documented volume-permission behavior.

## Scope

The runtime applies non-root identity, dropped capabilities, `no-new-privileges`, a read-only root filesystem, CPU/memory/PID bounds, and a separate workspace volume. These controls reduce risk but do not replace kernel isolation, a hardened Docker daemon, network policy, or human review. Existing legacy desktop-container functionality has separate behavior and should be treated as privileged infrastructure.
