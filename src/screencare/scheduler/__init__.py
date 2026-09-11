"""Clock/FakeClock, the central deadline scheduler, and the shared
DeadlineBudget helper engines use to survive sleep/idle correctly.

The single scheduling mechanism the architecture requires, in place of many
independent ``QTimer``s (``ScreenCare — Technical.md`` section 11;
``ScreenCare — Implementation Standards.md`` section 8).
"""
