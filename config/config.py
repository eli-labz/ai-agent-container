import os
import argparse
import secrets

def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('--port', type=int, default=5000)
	parser.add_argument('--debug', action='store_true')
	
	return parser.parse_known_args()[0]

def configure_app(app, config=None):
	data_dir = os.path.join(os.getcwd(), 'data')
	app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('AI_AGENT_CONTAINER_DATABASE_URL') or 'sqlite:///' + os.path.join(data_dir, 'flowcase.db')
	app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
	app.config['AI_AGENT_CONTAINER_ENV'] = os.environ.get('AI_AGENT_CONTAINER_ENV', 'development')
	app.config['AI_AGENT_CONTAINER_HOST'] = os.environ.get('AI_AGENT_CONTAINER_HOST', '0.0.0.0')
	app.config['AI_AGENT_CONTAINER_PORT'] = int(os.environ.get('AI_AGENT_CONTAINER_PORT', '5000'))
	app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
	app.config['SESSION_COOKIE_HTTPONLY'] = True
	app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
	app.config['SESSION_COOKIE_SECURE'] = app.config['AI_AGENT_CONTAINER_ENV'] == 'production'
	
	os.makedirs(data_dir, exist_ok=True)
	
	# Load secret key
	secret_key = os.environ.get('SECRET_KEY')
	if not secret_key and not os.path.exists(os.path.join(data_dir, 'secret_key')):
		with open(os.path.join(data_dir, 'secret_key'), "w") as f:
			f.write(secrets.token_urlsafe(48))
	if not secret_key:
		with open(os.path.join(data_dir, 'secret_key'), "r") as f:
			secret_key = f.read()
	app.secret_key = secret_key
	
	if config:
		app.config.update(config)
		
	return app 