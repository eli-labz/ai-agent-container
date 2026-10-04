import docker


class RuntimeUnavailable(RuntimeError):
	pass


class ContainerRuntime:
	"""Docker-backed runtime; agent containers never receive Docker API access."""

	def __init__(self, client=None):
		self.client = client

	def _client(self):
		if self.client is None:
			try:
				self.client = docker.from_env()
				self.client.ping()
			except docker.errors.DockerException as exc:
				raise RuntimeUnavailable("Docker runtime is unavailable.") from exc
		return self.client

	@staticmethod
	def _memory_bytes(value):
		unit = value[-2:]
		multiplier = 1024 * 1024 if unit == "Mi" else 1024 * 1024 * 1024
		return int(value[:-2]) * multiplier

	def create(self, agent):
		client = self._client()
		definition = agent.definition
		spec = definition["spec"]
		workspace_name = f"ai-agent-container-workspace-{agent.id}"
		client.volumes.create(name=workspace_name, labels={"ai-agent-container.agent": agent.id})
		resources = spec["resources"]
		cpu_quota = max(10000, int(float(resources["cpu"]) * 100000))
		user = spec["runtime"].get("user", "10000:10000")
		try:
			container = client.containers.create(
				image=spec["runtime"]["image"],
				command=spec["runtime"].get("command"),
			name=f"ai-agent-container-agent-{agent.id}",
			labels={"ai-agent-container.agent": agent.id},
			detach=True,
			working_dir="/workspace",
			user=user,
			volumes={workspace_name: {"bind": "/workspace", "mode": "rw" if spec["capabilities"]["filesystem"]["write"] else "ro"}},
			read_only=True,
			security_opt=["no-new-privileges:true"],
			cap_drop=["ALL"],
			pids_limit=resources["pids"],
			mem_limit=self._memory_bytes(resources["memory"]),
			cpu_period=100000,
			cpu_quota=cpu_quota,
			network_mode="bridge" if spec["capabilities"]["network"]["enabled"] else "none",
				tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
			)
		except Exception:
			try:
				client.volumes.get(workspace_name).remove()
			except Exception:
				pass
			raise
		return container.id, workspace_name

	def get(self, container_id):
		return self._client().containers.get(container_id)

	def inspect(self, container_id):
		container = self.get(container_id)
		container.reload()
		state = container.attrs.get("State", {})
		return {"status": state.get("Status", "unknown"), "running": state.get("Running", False), "image": container.attrs.get("Config", {}).get("Image")}

	def start(self, container_id):
		self.get(container_id).start()

	def stop(self, container_id):
		self.get(container_id).stop(timeout=10)

	def restart(self, container_id):
		self.get(container_id).restart(timeout=10)

	def pause(self, container_id):
		self.get(container_id).pause()

	def resume(self, container_id):
		self.get(container_id).unpause()

	def terminate(self, container_id, workspace_volume=None, persistent=True):
		self.get(container_id).remove(force=True)
		if workspace_volume and not persistent:
			self.remove_workspace(workspace_volume)

	def remove_workspace(self, workspace_volume):
		self._client().volumes.get(workspace_volume).remove()

	def logs(self, container_id, tail=200):
		return self.get(container_id).logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")