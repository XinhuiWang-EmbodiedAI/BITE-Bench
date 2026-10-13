"""Run with `uv run python scripts/check_environment.py`."""

import json

from bitebench.environment import doctor

print(json.dumps(doctor(), indent=2))
