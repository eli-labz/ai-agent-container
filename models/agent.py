import uuid

from sqlalchemy.sql import func

from __init__ import db


class Agent(db.Model):
	__tablename__ = "agent"

	id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	owner_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False, index=True)
	name = db.Column(db.String(80), nullable=False)
	description = db.Column(db.String(500), nullable=True)
	definition = db.Column(db.JSON, nullable=False)
	status = db.Column(db.String(20), nullable=False, default="created")
	container_id = db.Column(db.String(64), nullable=True)
	workspace_volume = db.Column(db.String(128), nullable=True)
	created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
	updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AgentTask(db.Model):
	__tablename__ = "agent_task"

	id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	agent_id = db.Column(db.String(36), nullable=False, index=True)
	owner_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False, index=True)
	title = db.Column(db.String(200), nullable=False)
	instructions = db.Column(db.Text, nullable=False)
	status = db.Column(db.String(30), nullable=False, default="queued")
	result = db.Column(db.Text, nullable=True)
	error = db.Column(db.Text, nullable=True)
	created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
	started_at = db.Column(db.DateTime, nullable=True)
	completed_at = db.Column(db.DateTime, nullable=True)


class AgentEvent(db.Model):
	__tablename__ = "agent_event"

	id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	event_type = db.Column(db.String(80), nullable=False, index=True)
	owner_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False, index=True)
	agent_id = db.Column(db.String(36), nullable=True, index=True)
	task_id = db.Column(db.String(36), nullable=True)
	actor = db.Column(db.String(80), nullable=False)
	metadata_json = db.Column(db.JSON, nullable=False, default=dict)
	created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)