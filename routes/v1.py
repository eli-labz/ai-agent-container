from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from __init__ import db
from models.agent import Agent, AgentEvent, AgentTask
from services.agent_definition import DefinitionError, parse_agent_definition
from services.container_runtime import ContainerRuntime, RuntimeUnavailable


api_v1_bp = Blueprint("api_v1", __name__)
runtime = ContainerRuntime()


@api_v1_bp.before_request
def require_api_authentication():
	if request.endpoint in {"api_v1.health", "api_v1.readiness"}:
		return None
	if not current_user.is_authenticated:
		return _error("AUTHENTICATION_REQUIRED", "Authentication is required.", 401)


def _error(code, message, status):
	return jsonify({"error": {"code": code, "message": message}}), status


def _agent_json(agent):
	return {
		"id": agent.id,
		"name": agent.name,
		"description": agent.description,
		"status": agent.status,
		"definition": agent.definition,
		"created_at": agent.created_at.isoformat() if agent.created_at else None,
	}


def _event(agent, event_type, metadata=None, task_id=None):
	db.session.add(AgentEvent(
		event_type=event_type,
		owner_id=current_user.id,
		agent_id=agent.id if agent else None,
		task_id=task_id,
		actor=current_user.username,
		metadata_json=metadata or {},
	))


def _owned_agent(agent_id):
	return Agent.query.filter_by(id=agent_id, owner_id=current_user.id).first()


@api_v1_bp.get("/health")
def health():
	return jsonify({"status": "ok", "service": "ai-agent-container-control-plane"})


@api_v1_bp.get("/readiness")
def readiness():
	try:
		db.session.execute(db.text("SELECT 1"))
		return jsonify({"status": "ready"})
	except Exception:
		return _error("NOT_READY", "Metadata store is unavailable.", 503)


@api_v1_bp.route("/agents", methods=["GET", "POST"])
def agents():
	if request.method == "GET":
		return jsonify({"agents": [_agent_json(agent) for agent in Agent.query.filter_by(owner_id=current_user.id).order_by(Agent.created_at.desc()).all()]})
	data = request.get_json(silent=True)
	if not isinstance(data, dict):
		return _error("INVALID_REQUEST", "Request body must be a JSON object.", 400)
	try:
		definition = parse_agent_definition(data.get("definition", data))
	except DefinitionError as exc:
		return _error("INVALID_AGENT_DEFINITION", str(exc), 400)
	metadata = definition["metadata"]
	if Agent.query.filter_by(owner_id=current_user.id, name=metadata["name"]).first():
		return _error("AGENT_NAME_EXISTS", "An agent with this name already exists.", 409)
	agent = Agent(
		owner_id=current_user.id,
		name=metadata["name"],
		description=metadata.get("description"),
		definition=definition,
	)
	db.session.add(agent)
	db.session.flush()
	_event(agent, "agent.created")
	db.session.commit()
	return jsonify(_agent_json(agent)), 201


@api_v1_bp.get("/agents/<agent_id>")
def get_agent(agent_id):
	agent = _owned_agent(agent_id)
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	return jsonify(_agent_json(agent))


@api_v1_bp.patch("/agents/<agent_id>")
def update_agent(agent_id):
	agent = _owned_agent(agent_id)
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	if agent.container_id:
		return _error("RUNTIME_EXISTS", "Stop and delete the runtime before changing its definition.", 409)
	data = request.get_json(silent=True)
	if not isinstance(data, dict):
		return _error("INVALID_REQUEST", "Request body must be a JSON object.", 400)
	try:
		definition = parse_agent_definition(data.get("definition", data))
	except DefinitionError as exc:
		return _error("INVALID_AGENT_DEFINITION", str(exc), 400)
	new_name = definition["metadata"]["name"]
	duplicate = Agent.query.filter(Agent.owner_id == current_user.id, Agent.name == new_name, Agent.id != agent.id).first()
	if duplicate:
		return _error("AGENT_NAME_EXISTS", "An agent with this name already exists.", 409)
	agent.name = new_name
	agent.description = definition["metadata"].get("description")
	agent.definition = definition
	_event(agent, "agent.updated")
	db.session.commit()
	return jsonify(_agent_json(agent))


@api_v1_bp.delete("/agents/<agent_id>")
def delete_agent(agent_id):
	agent = _owned_agent(agent_id)
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	try:
		if agent.container_id:
			runtime.terminate(agent.container_id, agent.workspace_volume, agent.definition["spec"]["workspace"]["persistent"])
		if agent.workspace_volume:
			runtime.remove_workspace(agent.workspace_volume)
	except Exception:
		db.session.rollback()
		return _error("RUNTIME_OPERATION_FAILED", "The agent runtime or workspace could not be removed; the agent was not deleted.", 502)
	_event(agent, "agent.terminated")
	db.session.delete(agent)
	db.session.commit()
	return "", 204


@api_v1_bp.post("/agents/<agent_id>/<action>")
def agent_action(agent_id, action):
	agent = _owned_agent(agent_id)
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	if action not in {"create", "start", "stop", "restart", "pause", "resume", "terminate"}:
		return _error("ACTION_NOT_FOUND", "The requested agent action is not supported.", 404)
	if action == "create" and agent.container_id:
		return _error("RUNTIME_EXISTS", "The agent runtime already exists.", 409)
	if action not in {"create", "start"} and not agent.container_id:
		return _error("RUNTIME_NOT_CREATED", "The agent runtime has not been created.", 409)
	created_container = False
	created_container_id = None
	created_workspace_volume = None
	try:
		if action == "create" or (action == "start" and not agent.container_id):
			if action == "start":
				agent.status = "starting"
				db.session.commit()
			agent.container_id, agent.workspace_volume = runtime.create(agent)
			created_container_id = agent.container_id
			created_workspace_volume = agent.workspace_volume
			created_container = True
			if action == "start":
				runtime.start(agent.container_id)
		elif action == "start":
			runtime.start(agent.container_id)
		elif action == "stop":
			agent.status = "stopping"
			db.session.commit()
			runtime.stop(agent.container_id)
		elif action == "restart":
			agent.status = "starting"
			db.session.commit()
			runtime.restart(agent.container_id)
		elif action == "pause":
			runtime.pause(agent.container_id)
		elif action == "resume":
			runtime.resume(agent.container_id)
		else:
			runtime.terminate(agent.container_id, agent.workspace_volume, agent.definition["spec"]["workspace"]["persistent"])
			agent.container_id = None
			agent.status = "terminated"
		if action in {"start", "restart", "resume"}:
			agent.status = "running"
		elif action == "stop":
			agent.status = "stopped"
		elif action == "pause":
			agent.status = "paused"
		elif action == "create":
			agent.status = "created"
		event_types = {"create": "agent.runtime_created", "start": "agent.started", "stop": "agent.stopped", "restart": "agent.restarted", "pause": "agent.paused", "resume": "agent.resumed", "terminate": "agent.terminated"}
		_event(agent, event_types[action])
		db.session.commit()
	except RuntimeUnavailable as exc:
		db.session.rollback()
		if created_container:
			try:
				runtime.terminate(created_container_id, created_workspace_volume, False)
			except Exception:
				pass
		agent.status = "failed"
		db.session.commit()
		return _error("RUNTIME_UNAVAILABLE", str(exc), 503)
	except Exception as exc:
		db.session.rollback()
		if created_container:
			try:
				runtime.terminate(agent.container_id, agent.workspace_volume, False)
			except Exception:
				pass
		agent.status = "failed"
		db.session.commit()
		return _error("RUNTIME_OPERATION_FAILED", "The Docker runtime operation failed.", 502)
	return jsonify(_agent_json(agent))


@api_v1_bp.get("/agents/<agent_id>/logs")
def agent_logs(agent_id):
	agent = _owned_agent(agent_id)
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	if not agent.container_id:
		return _error("RUNTIME_NOT_CREATED", "The agent runtime has not been created.", 409)
	try:
		return jsonify({"logs": runtime.logs(agent.container_id)})
	except Exception:
		return _error("RUNTIME_UNAVAILABLE", "Agent runtime logs are unavailable.", 502)


@api_v1_bp.get("/agents/<agent_id>/runtime")
def inspect_agent_runtime(agent_id):
	agent = _owned_agent(agent_id)
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	if not agent.container_id:
		return _error("RUNTIME_NOT_CREATED", "The agent runtime has not been created.", 409)
	try:
		return jsonify(runtime.inspect(agent.container_id))
	except Exception:
		return _error("RUNTIME_UNAVAILABLE", "Agent runtime information is unavailable.", 502)


@api_v1_bp.route("/tasks", methods=["GET", "POST"])
def tasks():
	if request.method == "GET":
		return jsonify({"tasks": [{"id": task.id, "agent_id": task.agent_id, "title": task.title, "status": task.status, "created_at": task.created_at.isoformat() if task.created_at else None} for task in AgentTask.query.filter_by(owner_id=current_user.id).order_by(AgentTask.created_at.desc()).all()]})
	data = request.get_json(silent=True)
	if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"].strip() or len(data["title"]) > 200 or not isinstance(data.get("instructions"), str) or not data["instructions"].strip() or len(data["instructions"]) > 100000:
		return _error("INVALID_TASK", "title (1 to 200 characters) and instructions (1 to 100000 characters) are required.", 400)
	agent = _owned_agent(data.get("agent_id"))
	if not agent:
		return _error("AGENT_NOT_FOUND", "The requested agent does not exist.", 404)
	task = AgentTask(agent_id=agent.id, owner_id=current_user.id, title=data["title"].strip(), instructions=data["instructions"].strip())
	db.session.add(task)
	db.session.flush()
	_event(agent, "task.created", task_id=task.id)
	db.session.commit()
	return jsonify({"id": task.id, "agent_id": task.agent_id, "title": task.title, "status": task.status}), 201


@api_v1_bp.post("/tasks/<task_id>/cancel")
def cancel_task(task_id):
	task = AgentTask.query.filter_by(id=task_id, owner_id=current_user.id).first()
	if not task:
		return _error("TASK_NOT_FOUND", "The requested task does not exist.", 404)
	if task.status not in {"queued", "assigned", "running", "waiting_for_approval"}:
		return _error("INVALID_TASK_STATE", "Only active tasks can be cancelled.", 409)
	task.status = "cancelled"
	task.completed_at = datetime.now(timezone.utc)
	_event(Agent.query.filter_by(id=task.agent_id).first(), "task.cancelled", task_id=task.id)
	db.session.commit()
	return jsonify({"id": task.id, "status": task.status})


@api_v1_bp.get("/tasks/<task_id>")
def get_task(task_id):
	task = AgentTask.query.filter_by(id=task_id, owner_id=current_user.id).first()
	if not task:
		return _error("TASK_NOT_FOUND", "The requested task does not exist.", 404)
	return jsonify({"id": task.id, "agent_id": task.agent_id, "title": task.title, "instructions": task.instructions, "status": task.status, "result": task.result, "error": task.error, "created_at": task.created_at.isoformat() if task.created_at else None})


@api_v1_bp.get("/events")
def events():
	items = AgentEvent.query.filter_by(owner_id=current_user.id).order_by(AgentEvent.created_at.desc()).limit(100).all()
	return jsonify({"events": [{"id": item.id, "event_type": item.event_type, "agent_id": item.agent_id, "task_id": item.task_id, "actor": item.actor, "metadata": item.metadata_json, "timestamp": item.created_at.isoformat() if item.created_at else None} for item in items]})