import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from __init__ import create_app, db
from models.agent import Agent, AgentEvent, AgentTask
from models.user import User
from services.agent_definition import DefinitionError, parse_agent_definition
from services.container_runtime import ContainerRuntime


def valid_definition(name="test-agent"):
	return {
		"apiVersion": "ai-agent-container/v1",
		"kind": "Agent",
		"metadata": {"name": name, "description": "Test worker"},
		"spec": {"runtime": {"image": "python:3.12-slim", "command": ["python", "-c", "import time; time.sleep(10**9)"]}},
	}


class FakeRuntime:
	def __init__(self):
		self.calls = []

	def create(self, agent):
		self.calls.append("create")
		return "container-test", "workspace-test"

	def start(self, container_id):
		self.calls.append(("start", container_id))

	def stop(self, container_id):
		self.calls.append(("stop", container_id))

	def restart(self, container_id):
		self.calls.append(("restart", container_id))

	def pause(self, container_id):
		self.calls.append(("pause", container_id))

	def resume(self, container_id):
		self.calls.append(("resume", container_id))

	def terminate(self, container_id, workspace_volume=None, persistent=True):
		self.calls.append(("terminate", container_id, workspace_volume, persistent))

	def remove_workspace(self, workspace_volume):
		self.calls.append(("remove_workspace", workspace_volume))

	def logs(self, container_id):
		return "runtime output"

	def inspect(self, container_id):
		return {"status": "running", "running": True}


class AgentPlatformTests(unittest.TestCase):
	def setUp(self):
		self.previous_cwd = os.getcwd()
		self.temp_dir = tempfile.TemporaryDirectory()
		os.chdir(self.temp_dir.name)
		self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only", "SQLALCHEMY_DATABASE_URI": "sqlite://"})
		with self.app.app_context():
			db.create_all()
			self.user = User(username="operator", password="not-a-login", auth_token="test-token", groups="", usertype="Internal")
			db.session.add(self.user)
			db.session.commit()
			self.user_id = self.user.id
		self.client = self.app.test_client()
		with self.client.session_transaction() as session:
			session["_user_id"] = self.user_id
			session["_fresh"] = True

	def tearDown(self):
		with self.app.app_context():
			db.session.remove()
			db.drop_all()
		os.chdir(self.previous_cwd)
		self.temp_dir.cleanup()

	def test_health_and_authentication_errors(self):
		self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
		self.assertEqual(self.client.get("/api/v1/missing").status_code, 404)
		self.assertTrue(self.client.get("/api/v1/missing").is_json)
		anonymous = self.app.test_client().post("/api/v1/agents", json={})
		self.assertEqual(anonymous.status_code, 401, anonymous.get_data(as_text=True))
		self.assertEqual(anonymous.json["error"]["code"], "AUTHENTICATION_REQUIRED")

	def test_definition_rejects_bad_policy_root_user_and_limits(self):
		bad_policy = valid_definition()
		bad_policy["spec"]["approvalPolicy"] = {"mode": "silently-allow"}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(bad_policy)
		root_user = valid_definition()
		root_user["spec"]["runtime"]["user"] = "0:0"
		with self.assertRaises(DefinitionError):
			parse_agent_definition(root_user)
		bad_limits = valid_definition()
		bad_limits["spec"]["resources"] = {"pids": 5000}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(bad_limits)
		bad_command = valid_definition()
		bad_command["spec"]["runtime"]["command"] = "python -c 'unsafe shell string'"
		with self.assertRaises(DefinitionError):
			parse_agent_definition(bad_command)
		unsupported_memory = valid_definition()
		unsupported_memory["spec"]["memory"] = {"enabled": True}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(unsupported_memory)
		unsupported_filesystem = valid_definition()
		unsupported_filesystem["spec"]["capabilities"] = {"filesystem": {"read": False}}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(unsupported_filesystem)
		malformed_policy = valid_definition()
		malformed_policy["spec"]["approvalPolicy"] = {"mode": ["manual"]}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(malformed_policy)
		malformed_provider = valid_definition()
		malformed_provider["spec"]["model"] = {"provider": ["openai"]}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(malformed_provider)
		plaintext_credential = valid_definition()
		plaintext_credential["spec"]["model"] = {"credential": "AIzaSyExampleProviderKey"}
		with self.assertRaises(DefinitionError):
			parse_agent_definition(plaintext_credential)

	def test_agent_task_event_and_lifecycle_api(self):
		fake_runtime = FakeRuntime()
		with patch("routes.v1.runtime", fake_runtime):
			created = self.client.post("/api/v1/agents", json={"definition": valid_definition()})
			self.assertEqual(created.status_code, 201)
			agent_id = created.json["id"]
			defined_runtime = self.client.post(f"/api/v1/agents/{agent_id}/create")
			self.assertEqual(defined_runtime.json["status"], "created")
			started = self.client.post(f"/api/v1/agents/{agent_id}/start")
			self.assertEqual(started.status_code, 200)
			self.assertEqual(started.json["status"], "running")
			self.assertEqual(self.client.get(f"/api/v1/agents/{agent_id}/runtime").json["status"], "running")
			self.assertEqual(self.client.get(f"/api/v1/agents/{agent_id}/logs").json["logs"], "runtime output")
			task = self.client.post("/api/v1/tasks", json={"agent_id": agent_id, "title": "Inspect", "instructions": "Inspect files"})
			self.assertEqual(task.status_code, 201)
			task_id = task.json["id"]
			self.assertEqual(self.client.get(f"/api/v1/tasks/{task_id}").json["status"], "queued")
			self.assertEqual(self.client.post(f"/api/v1/tasks/{task_id}/cancel").json["status"], "cancelled")
			with self.app.app_context():
				self.assertTrue(any(item.event_type == "agent.started" for item in AgentEvent.query.all()))
			self.assertEqual(self.client.post(f"/api/v1/agents/{agent_id}/stop").json["status"], "stopped")
			self.assertEqual(self.client.post(f"/api/v1/agents/{agent_id}/terminate").json["status"], "terminated")
			self.assertEqual(self.client.delete(f"/api/v1/agents/{agent_id}").status_code, 204)
			self.assertIn(("remove_workspace", "workspace-test"), fake_runtime.calls)

	def test_definition_validation_is_returned_as_structured_input_error(self):
		bad = valid_definition()
		bad["spec"]["approvalPolicy"] = {"mode": "unknown"}
		response = self.client.post("/api/v1/agents", json={"definition": bad})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json["error"]["code"], "INVALID_AGENT_DEFINITION")

	def test_agent_records_are_scoped_to_the_authenticated_owner(self):
		created = self.client.post("/api/v1/agents", json={"definition": valid_definition()})
		self.assertEqual(created.status_code, 201)
		with self.app.app_context():
			other_user = User(username="another-operator", password="not-a-login", auth_token="another-test-token", groups="", usertype="Internal")
			db.session.add(other_user)
			db.session.commit()
			other_user_id = other_user.id
		other_client = self.app.test_client()
		with other_client.session_transaction() as session:
			session["_user_id"] = other_user_id
			session["_fresh"] = True
		agent_id = created.json["id"]
		self.assertEqual(other_client.get(f"/api/v1/agents/{agent_id}").status_code, 404)
		self.assertEqual(other_client.get("/api/v1/agents").json["agents"], [])
		task = other_client.post("/api/v1/tasks", json={"agent_id": agent_id, "title": "Unauthorized", "instructions": "Must not be accepted"})
		self.assertEqual(task.status_code, 404)

	def test_runtime_applies_least_privilege_options(self):
		class FakeVolumes:
			def create(self, **kwargs):
				self.created = kwargs

		class FakeContainers:
			def create(self, **kwargs):
				self.created = kwargs
				return SimpleNamespace(id="container-id")

		client = SimpleNamespace(volumes=FakeVolumes(), containers=FakeContainers())
		agent = SimpleNamespace(id="agent-id", definition=parse_agent_definition(valid_definition()))
		container_id, volume_name = ContainerRuntime(client).create(agent)
		settings = client.containers.created
		self.assertEqual(container_id, "container-id")
		self.assertEqual(volume_name, "ai-agent-container-workspace-agent-id")
		self.assertTrue(settings["read_only"])
		self.assertEqual(settings["user"], "10000:10000")
		self.assertEqual(settings["cap_drop"], ["ALL"])
		self.assertEqual(settings["security_opt"], ["no-new-privileges:true"])
		self.assertEqual(settings["network_mode"], "none")
		self.assertEqual(settings["pids_limit"], 256)
		self.assertEqual(settings["volumes"][volume_name]["mode"], "rw")
		self.assertEqual(settings["command"], ["python", "-c", "import time; time.sleep(10**9)"])


if __name__ == "__main__":
	unittest.main()