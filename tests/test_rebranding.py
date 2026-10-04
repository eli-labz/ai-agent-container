import re
import unittest
from pathlib import Path

import yaml

from services.agent_definition import parse_agent_definition


ROOT = Path(__file__).resolve().parents[1]
LEGACY_REFERENCE_PATHS = {
	".env.example",
	"INSTALL.md",
	"LICENSE",
	"MIGRATIONS.md",
	"config/config.py",
	"docker-compose.dev.yml",
	"docker-compose.yml",
	"routes/admin.py",
	"routes/auth.py",
	"routes/droplet.py",
	"static/js/dashboard/admin.js",
	"utils/docker.py",
	"web.Dockerfile",
}
SECRET_PATTERNS = (
	re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
	re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
	re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


class RepositoryRegressionTests(unittest.TestCase):
	def test_legacy_branding_is_confined_to_documented_compatibility_files(self):
		matches = set()
		for path in ROOT.rglob("*"):
			if not path.is_file() or path == Path(__file__) or ".git" in path.parts or "__pycache__" in path.parts:
				continue
			try:
				content = path.read_text(encoding="utf-8")
			except UnicodeDecodeError:
				continue
			if re.search(r"flowcase|flowcase\.org|flowcaseweb", content, re.IGNORECASE):
				matches.add(path.relative_to(ROOT).as_posix())
		self.assertLessEqual(matches, LEGACY_REFERENCE_PATHS, f"Undocumented legacy branding: {sorted(matches - LEGACY_REFERENCE_PATHS)}")

	def test_installation_guides_use_current_repository(self):
		for path in ("README.md", "QUICKSTART.md", "INSTALL.md"):
			self.assertIn("eli-labz/ai-agent-container", (ROOT / path).read_text(encoding="utf-8"))

	def test_agent_examples_pass_runtime_definition_validation(self):
		for path in sorted((ROOT / "examples/agents").glob("*.yaml")):
			with self.subTest(example=path.name):
				parse_agent_definition(yaml.safe_load(path.read_text(encoding="utf-8")))

	def test_no_common_live_token_formats_are_committed(self):
		for path in ROOT.rglob("*"):
			if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
				continue
			try:
				content = path.read_text(encoding="utf-8")
			except UnicodeDecodeError:
				continue
			for pattern in SECRET_PATTERNS:
				self.assertIsNone(pattern.search(content), f"Possible credential in {path.relative_to(ROOT)}")


if __name__ == "__main__":
	unittest.main()