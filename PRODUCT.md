# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Operators inside a small organization (a studio or in-house team) who turn a brand's brief into short vertical
video. They work in campaigns for a brand and its audiences, on a laptop at a desk and, between tasks, on a phone.
They are not editors: they judge ideas, hooks, storyboards and the final cut, and expect the machine to do the rest.
_Assumption, inferred from `CONTEXT.md` and the route design; not interviewed._

## Product Purpose
Leynor takes one idea to a rendered 9:16 Instagram Reel through a fixed six-step route (Spark, Hook, Board, Look,
Voice, Print). Success: a person states an idea once, chooses between concrete takes, approves a storyboard and a
cut, and receives an mp4 that meets Instagram's length, legibility and loudness limits.

## Positioning
The route is gated, not a free-form editor: every step leaves a recorded decision, and steps that can be checked
(hooks, voice timing, render checks) pass on evidence rather than on a click. Visuals are generated locally and
deterministically, with credits on record; nothing is stock or scraped.

## Operating Context
Organization → Project → Campaign → Reel, with a Brand and its Audiences beside projects. A campaign speaks to one
audience (name, wants, barrier). Long steps (TTS, alignment, render) run on a background worker; the person returns
to see results. Terms used in the interface: see `CONTEXT.md` (Route, Gate, Render, Brief, Audience, Goal).

## Capabilities and Constraints
- Reels run 60 to 180 seconds; overlays up to 44 characters and 3 to 7 words.
- A unit's goal is one of saves, shares, follows; a campaign's goal is prose.
- Islands may only GET; mutations are Django forms. Svelte never owns URLs or navigation.
- No publishing until Instagram credentials are configured; unavailable means an honest error, never a fake success.

## Evidence on Hand
No customer data, testimonials or metrics exist. Concepts may only cite the operator's idea and the campaign's
audience; nothing else is a source.

## Product Principles
1. One decision per screen: show what a person must judge, and why it passed or failed.
2. Evidence over clicks: checks that a machine can run, it runs.
3. Never invent a fact: drafts cite only what the operator supplied.
4. Waiting is visible: long work shows where it is and what comes next, without trapping the person.

## Accessibility & Inclusion
WCAG 2.2 AA. Keyboard-complete forms, polite live regions for background progress, reduced motion respected.
