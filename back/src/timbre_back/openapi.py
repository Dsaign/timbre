"""Write the committed spec: `uv run python -m timbre_back.openapi > openapi.json`."""

import json

from timbre_back.main import app

print(json.dumps(app.openapi(), indent=2))
