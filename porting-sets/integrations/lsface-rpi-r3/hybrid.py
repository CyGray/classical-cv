"""Hardware-team compatibility import for the r3 cascade.

Upstream PC code imports ``HybridCascade`` from ``hybrid``. Keep that module
name while the maintained implementation lives in ``hybrid_rpi.py``.
"""

from hybrid_rpi import HybridCascade, route_after_quality

__all__ = ["HybridCascade", "route_after_quality"]
