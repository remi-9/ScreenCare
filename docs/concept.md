# ScreenCare — Adaptive Focus & Wellness Companion

ScreenCare is a privacy-first desktop application that combines focused-work techniques with evidence-informed computer wellness habits.

The application is intended for people who spend many hours programming, studying, designing, writing, gaming, or otherwise working at a computer and who may become so absorbed in their work that they forget to rest their eyes, move around, hydrate, or take meaningful breaks.

Rather than operating as a collection of independent reminder timers, ScreenCare should organize the user's workday around intelligent **Focus → Recover → Focus** cycles.

## Core Concept: Adaptive Pomodoro

ScreenCare should include a Pomodoro-inspired focus system, but it should not assume that the traditional 25-minute focus / 5-minute break pattern is ideal for every person or task.

Provide three modes:

### Classic Pomodoro
25 minutes focused work followed by approximately 5 minutes of rest.

### Deep Focus
Approximately 45–50 minutes of focused work followed by a 5–10 minute off-screen recovery period.

Designed for programming, writing, design, research, and other tasks where interrupting the user every 25 minutes may disrupt productive flow.

### Adaptive Focus
The recommended ScreenCare mode.

Allow the user's focus interval to gradually adapt based on actual behavior and lightweight feedback.

The app can occasionally ask after a work session:

- Too short
- Just right
- Too long

Use this information to personalize future focus periods while continuing to discourage extremely long uninterrupted computer sessions.

The objective is not to maximize the amount of time spent working.

The objective is to help the user alternate between **high-quality concentration and genuine recovery**.

## Focus Sessions

When starting a session, optionally ask:

**"What do you want to accomplish?"**

Example:

> Finish authentication flow

Display a minimal focus timer without unnecessary visual distractions.

Track active computer use so time spent away from the computer does not incorrectly count as focused work.

## Micro Eye Breaks

A focus session should not require continuous staring at the screen.

During longer focus sessions, provide extremely subtle eye-rest prompts approximately every 20 minutes.

For example:

> 👀 Look somewhere far away for 20 seconds.

These should not end the focus session or create a disruptive notification.

They are brief visual resets inside the larger work cycle.

## Recovery Breaks

At the end of a focus interval, encourage the user to physically leave the computer rather than switching from work to social media on the same screen.

A break might display:

**Focus complete. Time for a reset.**

🚶 Walk around  
💧 Drink or refill water  
👀 Look into the distance  
🙆 Move your neck, shoulders, and body  

**Break: 07:00**

Break activities should be optional suggestions rather than mandatory instructions.

The application should particularly encourage standing and walking after long periods of sitting.

## Smart Hydration

Include an hourly hydration reminder.

However, hydration notifications should integrate with the focus system instead of blindly interrupting the user every 60 minutes.

For example, if a scheduled Focus Break occurs within several minutes of the hydration reminder, combine them:

> **Recovery break**
> Time to walk around, rest your eyes, and get some water.

Avoid prescribing a universal amount of water per hour. Allow users to optionally configure their own hydration targets.

## Idea Walk

Include a special **"I'm Stuck"** action available during focused work.

Activating it starts an optional short Idea Walk.

Example:

**Take a 5-minute Idea Walk**

Step away from the screen and walk around. Don't force yourself to immediately solve the problem. Give yourself space to generate possibilities.

When the user returns:

**Anything come to mind?**

Provide a small text box where the user can quickly capture an idea before returning to the task.

This feature is intended particularly for creative thinking, brainstorming, planning, writing, design, and situations where the user feels mentally stuck.

## Flow Protection

ScreenCare should protect productive concentration rather than blindly interrupting it.

When a focus interval ends, allow the user to:

- Start Break
- Finish Current Thought
- Extend 5 Minutes

Extensions should be limited so that "just five more minutes" cannot accidentally become several hours of continuous screen use.

The application should become gradually more noticeable when the user repeatedly postpones necessary recovery periods.

## Break Intelligence

ScreenCare should detect situations such as:

- User has walked away from the computer
- Computer is locked
- Computer is sleeping
- No keyboard/mouse activity
- Presentation/fullscreen activity
- Do Not Disturb mode

Timers and notifications should react intelligently to these states.

For example, if the user naturally leaves the computer for ten minutes, ScreenCare should recognize that recovery time rather than immediately telling them to take another break when they return.

## Focus & Wellness Dashboard

The dashboard should emphasize useful behavioral patterns rather than raw screen time.

Show metrics including:

- Focus sessions completed
- Total focused time
- Average focus-session length
- Longest uninterrupted computer session
- Recovery breaks taken
- Recovery breaks skipped
- Walking breaks
- Eye-rest prompts
- Hydration check-ins
- Daily active screen time
- Optional headache/eye-strain/fatigue check-ins

Show trends over days and weeks so users can learn what working patterns feel best for them.

Avoid turning wellness into a stressful productivity competition.

## Guiding Philosophy

ScreenCare should follow this principle:

**Protect focus when focus is valuable. Interrupt when recovery is valuable.**

The application should not constantly nag the user.

Eye care, hydration, movement, posture, focus management, and screen-time awareness should work together as one coordinated system.

Instead of five unrelated notifications, ScreenCare should ideally produce one useful intervention at the right moment.

The long-term experience should feel like:

**Focus deeply → step away → move → hydrate → reset mentally → return refreshed.**

ScreenCare is a wellness and productivity-support tool, not a medical device. It should never claim to diagnose, prevent, or cure headaches or other medical conditions.