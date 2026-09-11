"""Idle / lock / sleep-wake activity monitoring, behind an OS-agnostic
interface (``ActivityProvider`` / ``PowerMonitor`` protocols).

Not yet implemented. Planned for Phase 5 — First platform integration,
starting with Windows. Domain and engine code must never import platform
APIs directly — only through this package's interfaces.
"""
