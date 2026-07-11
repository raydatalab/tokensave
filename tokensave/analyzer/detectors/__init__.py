"""
Waste detector registry.

Import detector modules here to register them with the analyzer engine.
"""

# Import detectors to trigger auto-registration via __init_subclass__
from tokensave.analyzer.detectors import duplicates as _  # noqa: F401
from tokensave.analyzer.detectors import context_bloat as _  # noqa: F401
from tokensave.analyzer.detectors import model_mismatch as _  # noqa: F401
from tokensave.analyzer.detectors import heartbeat as _  # noqa: F401
