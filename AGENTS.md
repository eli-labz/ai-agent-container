# Repository Agent Notes

Read `.github/copilot-instructions.md` before changing this repository. Agent API/runtime behavior is documented in `ARCHITECTURE.md`; known unsupported features are listed in `SETUP.md` and `README.md`.

Run `python -m unittest discover -s tests -v` after changes. Use mocked Docker clients in tests, keep Agent containers restricted, and do not claim queued tasks execute until a durable worker exists. Preserve legacy desktop-container compatibility and upstream license attribution unless a tested migration is provided.