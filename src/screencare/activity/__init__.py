"""Idle / lock / sleep-wake activity monitoring, behind an OS-agnostic
interface (``ActivityProvider`` / ``PowerMonitor`` / ``AutostartService``
protocols in ``base.py``, and the Qt-free ``PresenceMonitor`` in
``presence_monitor.py``).

Implemented as of Phase 5 — First platform integration. Domain and engine
code never imports platform APIs directly -- only through this package's
interfaces; the concrete Windows adapter lives in ``screencare.platform``.
"""
