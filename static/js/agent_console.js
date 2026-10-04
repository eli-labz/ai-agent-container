const notice = document.querySelector('#notice');
const agentList = document.querySelector('#agent-list');

async function api(path, options = {}) {
	const response = await fetch(`/api/v1${path}`, {
		credentials: 'same-origin',
		headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
		...options,
	});
	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		throw new Error(body.error?.message || `Request failed (${response.status})`);
	}
	return response.status === 204 ? null : response.json();
}

function announce(message, isError = false) {
	notice.textContent = message;
	notice.classList.toggle('error', isError);
	notice.hidden = false;
}

function button(label, action, agentId) {
	const element = document.createElement('button');
	element.className = 'button';
	element.type = 'button';
	element.textContent = label;
	element.addEventListener('click', action === 'logs' ? () => showLogs(agentId) : () => runAction(agentId, action));
	return element;
}

async function loadAgents() {
	try {
		const { agents } = await api('/agents');
		agentList.replaceChildren();
		document.querySelector('#agent-count').textContent = agents.length;
		const taskAgent = document.querySelector('#task-agent');
		taskAgent.replaceChildren();
		for (const agent of agents) {
			const row = document.createElement('article');
			row.className = 'agent-row';
			const details = document.createElement('div');
			const heading = document.createElement('h3');
			heading.textContent = agent.name;
			const description = document.createElement('p');
			description.textContent = agent.description || agent.definition.spec.runtime.image;
			const status = document.createElement('span');
			status.className = `status ${agent.status}`;
			status.textContent = agent.status;
			details.append(heading, description, status);
			const actions = document.createElement('div');
			actions.className = 'agent-actions';
			for (const action of ['start', 'stop', 'restart', 'pause', 'resume', 'logs']) actions.append(button(action, action, agent.id));
			row.append(details, actions);
			agentList.append(row);
			const option = document.createElement('option');
			option.value = agent.id;
			option.textContent = agent.name;
			taskAgent.append(option);
		}
		if (!agents.length) agentList.innerHTML = '<p class="empty">No agents yet. Create one to get started.</p>';
	} catch (error) { announce(error.message, true); }
}

async function runAction(agentId, action) {
	try {
		await api(`/agents/${agentId}/${action}`, { method: 'POST' });
		announce(`Agent ${action} request completed.`);
		await refresh();
	} catch (error) { announce(error.message, true); }
}

async function showLogs(agentId) {
	try {
		const { logs } = await api(`/agents/${agentId}/logs`);
		document.querySelector('#logs-content').textContent = logs;
		document.querySelector('#logs-dialog').showModal();
	} catch (error) { announce(error.message, true); }
}

async function loadTasks() {
	try {
		const { tasks } = await api('/tasks');
		const target = document.querySelector('#task-list');
		target.replaceChildren();
		for (const task of tasks.slice(0, 10)) {
			const item = document.createElement('div');
			item.className = 'table-item';
			const title = document.createElement('strong');
			title.textContent = task.title;
			const status = document.createElement('span');
			status.textContent = task.status;
			item.append(title, status);
			target.append(item);
		}
		if (!tasks.length) target.innerHTML = '<p class="empty">No tasks submitted.</p>';
	} catch (error) { announce(error.message, true); }
}

async function loadEvents() {
	try {
		const { events } = await api('/events');
		const target = document.querySelector('#event-list');
		target.replaceChildren();
		for (const event of events.slice(0, 10)) {
			const item = document.createElement('div');
			item.className = 'table-item';
			const name = document.createElement('strong');
			name.textContent = event.event_type;
			const timestamp = document.createElement('span');
			timestamp.textContent = event.timestamp ? new Date(event.timestamp).toLocaleString() : '';
			item.append(name, timestamp);
			target.append(item);
		}
		if (!events.length) target.innerHTML = '<p class="empty">No events recorded.</p>';
	} catch (error) { announce(error.message, true); }
}

async function refresh() { await Promise.all([loadAgents(), loadTasks(), loadEvents()]); }

document.querySelector('#create-agent').addEventListener('click', async () => {
	try {
		await api('/agents', { method: 'POST', body: JSON.stringify({ definition: document.querySelector('#definition').value }) });
		announce('Agent definition created.');
		await refresh();
	} catch (error) { announce(error.message, true); }
});

document.querySelector('#submit-task').addEventListener('click', async () => {
	try {
		await api('/tasks', { method: 'POST', body: JSON.stringify({
			agent_id: document.querySelector('#task-agent').value,
			title: document.querySelector('#task-title').value,
			instructions: document.querySelector('#task-instructions').value,
		}) });
		announce('Task added to the queue.');
		document.querySelector('#task-title').value = '';
		document.querySelector('#task-instructions').value = '';
		await refresh();
	} catch (error) { announce(error.message, true); }
});

document.querySelector('#refresh-button').addEventListener('click', refresh);
document.querySelector('#close-logs').addEventListener('click', () => document.querySelector('#logs-dialog').close());
refresh();