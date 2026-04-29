import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

# Mock weasyprint's HTML class globally to prevent import errors on systems
# without required native libraries (libgobject, Pango, Cairo, etc.)
# Use a minimal stub that only exposes HTML to catch import typos or unexpected attribute access
sys.modules["weasyprint"] = SimpleNamespace(HTML=MagicMock())
