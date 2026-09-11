"""Application wiring: turning a running process into a Qt application.

This package is intentionally thin. It must never contain focus, break,
hydration, or coordinator logic — that lives in ``screencare.engines`` from
Phase 2 onward. See ARCHITECTURE.md.
"""
