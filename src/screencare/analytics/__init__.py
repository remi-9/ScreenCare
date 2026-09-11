"""Dashboard statistics over the local SQLite history.

``summary.py`` is pure aggregation (no SQLite, no Qt) over rows the caller
already fetched with a repository's ``list_since`` — see
``ScreenCare — Technical.md`` section 42 on running dashboard queries only
when something actually warrants recomputing them, never on a timer.
"""
