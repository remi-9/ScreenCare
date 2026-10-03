"""Every user-facing message, with a few variations each.

Tone: calm, kind, short. No exclamation marks, no guilt, no scores, and no
medical claims. Rules pick server-side messages with `pick`, seeded by the
moment, so the same moment always gives the same text (tests stay
deterministic) while real use feels varied. The page receives `UI` and picks
one variant per phase, so text never changes mid-phase.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import datetime


def pick(options: Sequence[str], now: datetime, salt: str = "") -> str:
    return random.Random(f"{salt}|{now.isoformat()}").choice(options)


# -- notifications and banners (chosen by rules.py) -------------------------------

RECOVERY_TITLES = [
    "Time for a reset.",
    "Focus block complete.",
    "Nicely focused.",
    "Break time.",
]

# Keyed by (include_water, include_eyes). Bodies that include water always say
# "water"; bodies that don't never do. Tests hold this contract.
RECOVERY_BODIES = {
    (True, True): [
        "Walk around, rest your eyes, and get some water.",
        "Get some water, stretch your legs, and give your eyes a distant view.",
        "Refill your water, take a short walk, and look at something far away.",
    ],
    (True, False): [
        "Walk around and get some water.",
        "Stretch your legs and refill your water.",
        "A short walk and a glass of water would be perfect.",
    ],
    (False, True): [
        "Walk around and rest your eyes.",
        "Stand up, stretch, and look at something far away.",
        "Give your eyes a rest and your legs a walk.",
    ],
    (False, False): [
        "Stand up and walk around for a few minutes.",
        "Stretch, move, and step away from the screen.",
        "A few minutes on your feet will help the next block.",
    ],
}

BREAK_OVER_TITLES = ["Break's up.", "Break complete.", "That was your break."]
BREAK_OVER_BODIES = [
    "Come back whenever you're ready.",
    "Ease back in when it feels right.",
    "No rush. Start your next block when you're ready.",
]

IDEA_WALK_OVER_TITLES = ["Welcome back.", "How was the walk?", "Back from your walk?"]
IDEA_WALK_OVER_BODIES = [
    "Anything come to mind?",
    "Jot down anything that surfaced.",
    "Capture an idea before it slips away.",
]

HYDRATION_TITLES = ["Hydration", "Water break", "Time for water"]
HYDRATION_BODIES = [
    "Time to drink some water.",
    "A good moment for a glass of water.",
    "Your water bottle misses you.",
]

EYE_REST = [
    "👀 Look at something far away for 20 seconds.",
    "👀 Find the farthest thing you can see and rest your eyes on it.",
    "👀 Give your eyes 20 seconds on something distant.",
    "👀 Blink slowly and look out a window for a moment.",
]

WELCOME_BACK = [
    "Welcome back. That counted as your break.",
    "Welcome back. Your time away counted as a break.",
    "Nice break. You were away long enough for it to count.",
]


# -- on-screen copy (chosen by the page, one variant per phase) ------------------------
# Each entry is (headline, supporting line).

UI: dict[str, list[tuple[str, str]] | list[str]] = {
    "idle": [
        (
            "Ready for a focus block?",
            "Focus deeply, then step away. Reminders are folded into your breaks.",
        ),
        (
            "What's next on your mind?",
            "Pick a rhythm and settle in. ScreenCare will tell you when to step away.",
        ),
        ("Let's find your focus.", "One block at a time, with a real break after each."),
        (
            "Fresh block, fresh start.",
            "Set an intention if you like, then let the timer keep time for you.",
        ),
    ],
    "focusing": [
        (
            "In the zone.",
            "Nothing to manage. ScreenCare will tell you when it's time to step away.",
        ),
        ("Deep in it.", "The clock is keeping time so you don't have to."),
        ("Heads down.", "Your break is already planned. Just focus."),
        ("Steady and focused.", "Everything else can wait until your break."),
    ],
    "overtime": [
        ("A little extra time.", "Wrap up the thought you're on. Your break is close."),
        ("Bonus minutes.", "Find a good stopping point, then step away."),
        ("Almost there.", "Land this thought. The break will still be here."),
    ],
    "paused": [
        ("Paused.", "Take your time. The clock is holding."),
        ("On hold.", "Nothing's ticking. Pick it back up whenever you're ready."),
        ("Taking a moment.", "Your block will be right here when you return."),
    ],
    "recovery": [
        (
            "Focus complete. Time for a reset.",
            "Leave the screen for a few minutes. Walk, get some water, look at something far away.",
        ),
        (
            "Nicely done. Time to step away.",
            "Stand up, stretch, and let your eyes rest on something distant.",
        ),
        (
            "That's a block. Your break is ready.",
            "A few minutes away from the screen makes the next block better.",
        ),
        ("Good work. Now recover.", "Move a little, drink some water, and let your mind wander."),
    ],
    "postponed": [
        (
            "Your break is waiting.",
            "Still going? That's fine once. A short walk often unlocks the next step.",
        ),
        (
            "Your break's still here.",
            "One more push is fine. The walk will help the next idea land.",
        ),
        ("Ready when you are.", "Finish the thought, then give yourself a real break."),
    ],
    "postponed_max": [
        (
            "Time to step away.",
            "You've stretched this block as far as it goes. Your eyes and back will thank you.",
        ),
        ("This block is done.", "No more extensions this time. Get up, move, and come back fresh."),
        ("Break time, for real.", "You've earned this one. The work will keep for a few minutes."),
    ],
    "breaking": [
        ("Step away for a bit.", "A few ideas, only if they feel good:"),
        ("Time to move.", "Pick anything that sounds nice, or none at all:"),
        ("Away from the screen.", "Some ways to spend it, entirely optional:"),
    ],
    "idea_walk": [
        (
            "Take a 5-minute Idea Walk.",
            "Step away and walk around. Don't force a solution. Give yourself space for possibilities.",
        ),
        (
            "Walk it off.",
            "Let the problem sit in the background for five minutes. Ideas often show up when you stop chasing them.",
        ),
        (
            "Five minutes, no screen.",
            "Walk, look around, and let your mind wander. Jot down anything that surfaces.",
        ),
    ],
    "drink": [
        "💧 Nice. Logged a drink.",
        "💧 Logged. Your body thanks you.",
        "💧 Drink noted.",
        "💧 Hydrated. Logged it.",
    ],
}
