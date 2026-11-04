# The reel slug is derived, not typed

`Reel.slug` stays in the table but is computed from the title, numbered when the campaign already holds that slug. It is the stable key for the visual seed, the spec's identity and the composition id, so a human-readable key keeps renders reproducible and artefact names debuggable. It was removed from every form: no operator ever needs to type one, and the duplicate-slug error it used to raise is now a suffix nobody sees.

Considered and rejected: dropping the column and seeding off the UUID (same behaviour, but every artefact name becomes an opaque id), and deriving on the fly without storing (the seed would change when a title changed, silently rebuilding visuals).
