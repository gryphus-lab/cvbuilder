import sys
from unittest.mock import MagicMock

# Mock weasyprint's HTML class globally to prevent import errors on systems
# without required native libraries (libgobject, Pango, Cairo, etc.)
sys.modules["weasyprint"] = MagicMock()
