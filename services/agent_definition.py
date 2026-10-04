import re

import yaml


_IMAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$")
_MEMORY_PATTERN = re.compile(r"^[1-9][0-9]*(Mi|Gi)$")


class DefinitionError(ValueError):
	pass


def parse_agent_definition(payload):
	if isinstance(payload, str):
		try:
			definition = yaml.safe_load(payload)
		except yaml.YAMLError as exc:
			raise DefinitionError("Agent definition is not valid YAML.") from exc
	else:
		definition = payload

	if not isinstance(definition, dict):
		raise DefinitionError("Agent definition must be a YAML or JSON object.")
	if set(definition) != {"apiVersion", "kind", "metadata", "spec"}:
		raise DefinitionError("Agent definition contains unsupported top-level fields.")
	if definition.get("apiVersion") != "ai-agent-container/v1":
		raise DefinitionError("apiVersion must be 'ai-agent-container/v1'.")
	if definition.get("kind") != "Agent":
		raise DefinitionError("kind must be 'Agent'.")

	metadata = definition.get("metadata")
	spec = definition.get("spec")
	if not isinstance(metadata, dict) or not isinstance(spec, dict):
		raise DefinitionError("metadata and spec must be objects.")
	if set(metadata) - {"name", "description"}:
		raise DefinitionError("metadata contains unsupported fields.")
	if "description" in metadata and (not isinstance(metadata["description"], str) or len(metadata["description"]) > 500):
		raise DefinitionError("metadata.description must be a string of at most 500 characters.")
	allowed_spec = {"runtime", "model", "workspace", "resources", "capabilities", "tools", "memory", "approvalPolicy"}
	if set(spec) - allowed_spec:
		raise DefinitionError("spec contains unsupported fields.")

	name = metadata.get("name")
	if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?", name):
		raise DefinitionError("metadata.name must be a lowercase DNS-style name of 1 to 80 characters.")

	runtime = spec.get("runtime")
	if not isinstance(runtime, dict):
		raise DefinitionError("spec.runtime must be an object.")
	if set(runtime) - {"image", "user", "command"}:
		raise DefinitionError("spec.runtime contains unsupported fields.")
	image = runtime.get("image")
	if not isinstance(image, str) or not _IMAGE_PATTERN.fullmatch(image) or ".." in image:
		raise DefinitionError("spec.runtime.image must be a valid image reference.")
	user = runtime.get("user", "10000:10000")
	if not isinstance(user, str) or not re.fullmatch(r"[1-9][0-9]{0,5}(:[1-9][0-9]{0,5})?", user):
		raise DefinitionError("spec.runtime.user must be a non-root numeric UID[:GID].")
	runtime["user"] = user
	command = runtime.get("command")
	if command is not None and (
		not isinstance(command, list)
		or not 1 <= len(command) <= 64
		or any(not isinstance(argument, str) or not argument or "\x00" in argument for argument in command)
		or sum(len(argument) for argument in command) > 8192
	):
		raise DefinitionError("spec.runtime.command must be a bounded list of non-empty argument strings.")

	resources = spec.setdefault("resources", {})
	if not isinstance(resources, dict):
		raise DefinitionError("spec.resources must be an object.")
	if set(resources) - {"cpu", "memory", "pids"}:
		raise DefinitionError("spec.resources contains unsupported fields.")
	cpu = resources.get("cpu", "1")
	if isinstance(cpu, bool):
		raise DefinitionError("spec.resources.cpu must be a number between 0.1 and 8.")
	try:
		cpu_value = float(cpu)
	except (TypeError, ValueError) as exc:
		raise DefinitionError("spec.resources.cpu must be a number between 0.1 and 8.") from exc
	if not 0.1 <= cpu_value <= 8:
		raise DefinitionError("spec.resources.cpu must be between 0.1 and 8.")
	resources["cpu"] = cpu_value
	memory = resources.get("memory", "1Gi")
	if not isinstance(memory, str) or not _MEMORY_PATTERN.fullmatch(memory):
		raise DefinitionError("spec.resources.memory must be a positive value ending in Mi or Gi.")
	memory_bytes = int(memory[:-2]) * (1024 * 1024 if memory.endswith("Mi") else 1024 * 1024 * 1024)
	if memory_bytes > 64 * 1024 * 1024 * 1024:
		raise DefinitionError("spec.resources.memory cannot exceed 64Gi.")
	resources["memory"] = memory
	pids = resources.get("pids", 256)
	if isinstance(pids, bool) or not isinstance(pids, int) or not 1 <= pids <= 4096:
		raise DefinitionError("spec.resources.pids must be an integer between 1 and 4096.")
	resources["pids"] = pids

	workspace = spec.setdefault("workspace", {})
	if not isinstance(workspace, dict):
		raise DefinitionError("spec.workspace must be an object.")
	if set(workspace) - {"path", "persistent"}:
		raise DefinitionError("spec.workspace contains unsupported fields.")
	if workspace.get("path", "/workspace") != "/workspace":
		raise DefinitionError("spec.workspace.path must be '/workspace'.")
	workspace["path"] = "/workspace"
	if "persistent" in workspace and not isinstance(workspace["persistent"], bool):
		raise DefinitionError("spec.workspace.persistent must be a boolean.")
	workspace.setdefault("persistent", True)

	capabilities = spec.setdefault("capabilities", {})
	if not isinstance(capabilities, dict):
		raise DefinitionError("spec.capabilities must be an object.")
	if set(capabilities) - {"network", "filesystem"}:
		raise DefinitionError("spec.capabilities contains unsupported fields.")
	network = capabilities.setdefault("network", {})
	if not isinstance(network, dict) or set(network) - {"enabled"} or not isinstance(network.get("enabled", False), bool):
		raise DefinitionError("spec.capabilities.network.enabled must be a boolean.")
	capabilities["network"] = {"enabled": network.get("enabled", False)}
	filesystem = capabilities.setdefault("filesystem", {"read": True, "write": True})
	if not isinstance(filesystem, dict) or set(filesystem) - {"read", "write"}:
		raise DefinitionError("spec.capabilities.filesystem supports only read and write booleans.")
	if any(not isinstance(filesystem.get(permission, True), bool) for permission in ("read", "write")):
		raise DefinitionError("spec.capabilities.filesystem read and write settings must be booleans.")
	if filesystem.get("read", True) is False:
		raise DefinitionError("Disabling all filesystem reads is not supported by this runtime.")
	capabilities["filesystem"] = {"read": filesystem.get("read", True), "write": filesystem.get("write", True)}

	model = spec.get("model", {})
	if not isinstance(model, dict) or set(model) - {"provider", "model", "credential"}:
		raise DefinitionError("spec.model must be an object.")
	providers = {"openai", "anthropic", "google", "azure-openai", "openai-compatible", "ollama"}
	if "provider" in model and (not isinstance(model["provider"], str) or model["provider"] not in providers):
		raise DefinitionError("spec.model.provider is not a supported provider identifier.")
	if "model" in model and (not isinstance(model["model"], str) or not model["model"].strip()):
		raise DefinitionError("spec.model.model must be a non-empty string.")
	if "credential" in model and (not isinstance(model["credential"], str) or not re.fullmatch(r"[a-z][a-z0-9._-]{0,127}", model["credential"])):
		raise DefinitionError("spec.model.credential must be a credential identifier, not a secret value.")
	if isinstance(model.get("credential"), str) and model["credential"].lower().startswith(("sk-", "aiza", "bearer-")):
		raise DefinitionError("spec.model.credential must be a credential identifier, not a secret value.")

	approval_policy = spec.get("approvalPolicy", {"mode": "risk-based"})
	policy_mode = approval_policy.get("mode", "risk-based") if isinstance(approval_policy, dict) else None
	if not isinstance(approval_policy, dict) or set(approval_policy) - {"mode"} or not isinstance(policy_mode, str) or policy_mode not in {"risk-based", "manual", "always"}:
		raise DefinitionError("spec.approvalPolicy.mode must be risk-based, manual, or always.")
	spec["approvalPolicy"] = {"mode": policy_mode}

	tools = spec.setdefault("tools", [])
	if not isinstance(tools, list) or tools:
		raise DefinitionError("Tool definitions are not supported by this release; spec.tools must be empty.")

	memory = spec.get("memory", {"enabled": False})
	if not isinstance(memory, dict) or set(memory) - {"enabled"} or not isinstance(memory.get("enabled", False), bool):
		raise DefinitionError("spec.memory.enabled must be a boolean.")
	if memory.get("enabled", False):
		raise DefinitionError("Agent Memory is not implemented in this release; set spec.memory.enabled to false.")
	spec["memory"] = {"enabled": memory.get("enabled", False)}

	return definition