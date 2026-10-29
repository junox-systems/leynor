"""Compose HyperFrames HTML from visuals, cues and the master take.

Audio is mounted once, last, as the master. Scene windows come from cue starts,
so picture follows voice instead of padding audio to fit picture.

Art direction: warm dark editorial. Each scene is a layered frame (plate, glare,
ghost label, oversized numeral, rules, metadata), not a centred card. Five
layout variants keep five scenes from reading as one repeated slide. Captions
sit 30% up from the bottom, clear of the progress bar.
"""

from __future__ import annotations

import html
from pathlib import Path

from apps.projects.spec import ReelSpec
from apps.renders.design import Design

# h1 size, body top, numeral scale for each variant
VARIANTS = {
    1: {
        "size": 118,
        "top": 300,
        "numeral": 300,
        "ghost": "left",
        "right": 120,
        "ghosttop": 820,
    },
    2: {
        "size": 100,
        "top": 360,
        "numeral": 240,
        "ghost": "right",
        "right": 300,
        "ghosttop": 820,
    },
    3: {
        "size": 96,
        "top": 760,
        "numeral": 420,
        "ghost": "center",
        "right": 96,
        "ghosttop": 210,
    },
    4: {
        "size": 112,
        "top": 320,
        "numeral": 200,
        "ghost": "left",
        "right": 120,
        "ghosttop": 820,
    },
    5: {
        "size": 96,
        "top": 700,
        "numeral": 320,
        "ghost": "right",
        "right": 120,
        "ghosttop": 210,
    },
}

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  html, body {{ margin:0; width:1080px; height:1920px; background:{bg}; }}
  body {{ font-family:{font_display}; }}
  #root {{ position:relative; width:100%; height:100%; overflow:hidden;
          background:{bg}; }}
  .mount {{ position:absolute; inset:0; }}
</style>
</head>
<body>
<div id="root" data-composition-id="{cid}" data-width="1080" data-height="1920" data-duration="{total}">
{hosts}
{captions}
{audio}
</div>
<script>
  const host = gsap.timeline({{ paused: true }});
  host.to({{}}, {{ duration: {total} }});
  window.__timelines["{cid}"] = host;
</script>
</body>
</html>
"""

HOST = """  <div id="{sid}" class="mount" data-composition-id="{sid}"
       data-composition-src="compositions/{sid}.html"
       data-start="{start}" data-duration="{length}"
       data-track-index="1" data-width="1080" data-height="1920"></div>"""

CAPTION_HOST = """  <div id="captions" class="mount" data-composition-id="captions"
       data-track-kind="captions"
       data-composition-src="compositions/captions.html"
       data-start="0" data-duration="{total}"
       data-track-index="2" data-width="1080" data-height="1920"></div>"""

AUDIO = """  <audio id="voice" src="assets/voice.wav" data-start="0" data-duration="{total}" volume="1"></audio>"""

SCENE = """<!doctype html>
<html lang="en">
<head><meta charset="UTF-8" /></head>
<body>
<template>
<style>
  #root {{ position:absolute; inset:0; overflow:hidden; background:{bg};
          color:{fg}; font-family:{font_display};
          --accent:{accent}; --dim:{dim}; --line:{line}; }}
  .plate {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }}
  .veil {{ position:absolute; inset:0;
          background: radial-gradient(120% 80% at 78% 18%, rgba(13,12,10,0.10) 0%,
                    rgba(13,12,10,0.62) 58%, rgba(13,12,10,0.93) 100%); }}
  .glow {{ position:absolute; width:1200px; height:1200px; left:{glowx}px; top:{glowy}px;
          border-radius:50%; background:radial-gradient(circle,
          rgba(224,163,62,0.22) 0%, rgba(224,163,62,0.06) 45%, rgba(224,163,62,0) 70%);
          filter:blur(2px); }}
  .grain {{ position:absolute; inset:-60px; opacity:0.10; pointer-events:none;
           background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.55'/></svg>"); }}
  .ghost {{ position:absolute; left:{ghostleft}px; top:{ghosttop}px; font-size:{ghostsize}px; line-height:0.8;
           font-weight:800; letter-spacing:-0.05em; text-transform:uppercase;
           color:{fg}; opacity:0.055; white-space:nowrap; }}
  .numeral {{ position:absolute; right:64px; bottom:280px; font-size:{numeral}px; line-height:0.78;
             font-weight:800; letter-spacing:-0.07em; color:var(--accent); opacity:0.16; }}
  .frame {{ position:absolute; inset:44px; border:1px solid var(--line); }}
  .grid {{ position:absolute; inset:44px; }}
  .grid i {{ position:absolute; background:var(--line); }}
  .grid i.v1 {{ left:33.3%; top:0; bottom:0; width:1px; }}
  .grid i.v2 {{ left:66.6%; top:0; bottom:0; width:1px; }}
  .grid i.h1 {{ top:31%; left:0; right:0; height:1px; }}
  .topline {{ position:absolute; left:96px; right:96px; top:96px; display:flex;
             justify-content:space-between; align-items:baseline;
             font-family:{font_mono}; font-size:28px;
             letter-spacing:0.24em; text-transform:uppercase; }}
  .topline .kicker {{ color:var(--accent); }}
  .topline .index {{ color:var(--dim); }}
  .body {{ position:absolute; left:96px; right:{right}px; top:{top}px; }}
  .eyebrow {{ font-family:{font_mono}; font-size:28px; letter-spacing:0.26em;
             text-transform:uppercase; color:var(--dim); margin-bottom:30px; }}
  .rule {{ width:150px; height:4px; background:var(--accent); margin-bottom:34px; }}
  h1 {{ margin:0; font-size:{h1size}px; line-height:0.92; letter-spacing:-0.045em;
       font-weight:800; text-wrap:balance; }}
  .foot {{ position:absolute; left:96px; right:96px; bottom:70px; display:flex;
          justify-content:space-between; font-family:{font_mono};
          font-size:28px; letter-spacing:0.22em; text-transform:uppercase;
          color:var(--dim); }}
  .progress {{ position:absolute; left:44px; right:44px; bottom:40px; height:2px;
              background:var(--accent); transform-origin:left center; opacity:0.85; }}
  .wave {{ position:absolute; left:96px; width:888px; bottom:330px; opacity:0.6;
          mix-blend-mode:screen; }}
</style>
<div id="root" data-composition-id="{sid}">
  <img class="plate" id="{sid}-plate" src="{plate}" alt="" />
  <div class="veil"></div>
  <div class="glow" id="{sid}-glow"></div>
  <div class="grain" id="{sid}-grain"></div>
  <div class="grid" id="{sid}-grid"><i class="v1"></i><i class="v2"></i><i class="h1"></i></div>
  <div class="ghost" id="{sid}-ghost">{label}</div>
  <div class="numeral" id="{sid}-numeral">{n:02d}</div>
  <div class="frame" id="{sid}-frame"></div>
  <div class="topline" id="{sid}-topline">
    <span class="kicker">{kicker}</span><span class="index">{n:02d} / {count:02d}</span>
  </div>
  <div class="body" id="{sid}-body">
    <div class="eyebrow" id="{sid}-eyebrow">{label}</div>
    <div class="rule" id="{sid}-rule"></div>
    <h1 id="{sid}-title">{overlay}</h1>
  </div>
  <div class="foot" id="{sid}-foot"><span>lay with me</span><span>{n:02d}</span></div>
  <div class="progress" id="{sid}-progress"></div>
{wave}
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  tl.fromTo("#{sid}-title", {{ y: 46, opacity: 0 }},
            {{ y: 0, opacity: 1, duration: 0.85, ease: "power4.out" }}, 0.05);
  tl.fromTo("#{sid}-rule", {{ scaleX: 0, transformOrigin: "left center" }},
            {{ scaleX: 1, duration: 0.7, ease: "expo.out" }}, 0.0);
  tl.fromTo("#{sid}-eyebrow", {{ x: -18, opacity: 0 }},
            {{ x: 0, opacity: 1, duration: 0.6, ease: "power2.out" }}, 0.18);
  tl.fromTo("#{sid}-topline", {{ y: -16, opacity: 0 }},
            {{ y: 0, opacity: 1, duration: 0.6, ease: "power2.out" }}, 0.24);
  tl.fromTo("#{sid}-foot", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, 0.35);
  tl.fromTo("#{sid}-numeral", {{ y: 40, opacity: 0 }},
            {{ y: 0, opacity: 0.16, duration: 1.0, ease: "power3.out" }}, 0.1);
  tl.fromTo("#{sid}-grid", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.8 }}, 0.15);
  tl.fromTo("#{sid}-plate", {{ scale: 1.03 }},
            {{ scale: 1.08, duration: {length}, ease: "none" }}, 0);
  tl.fromTo("#{sid}-glow", {{ scale: 0.9, opacity: 0.7 }},
            {{ scale: 1.12, opacity: 1, duration: {length}, ease: "sine.inOut" }}, 0);
  tl.fromTo("#{sid}-ghost", {{ x: {ghostdx} }},
            {{ x: 0, duration: {length}, ease: "none" }}, 0);
  tl.fromTo("#{sid}-grain", {{ x: -30, y: 20 }},
            {{ x: 30, y: -20, duration: {length}, ease: "none" }}, 0);
  tl.fromTo("#{sid}-progress", {{ scaleX: 0 }},
            {{ scaleX: 1, duration: {length}, ease: "none" }}, 0);
  window.__timelines["{sid}"] = tl;
</script>
</template>
</body>
</html>
"""

CAPTIONS = """<!doctype html>
<html lang="en">
<head><meta charset="UTF-8" /></head>
<body>
<template>
<style>
  #root {{ position:absolute; inset:0; font-family:{font_display};
          color:{fg}; }}
  .cue {{ position:absolute; left:90px; right:90px; bottom:{caption_bottom}; text-align:center;
         font-size:{caption_size}px; line-height:1.22; font-weight:600; letter-spacing:-0.015em;
         text-shadow:0 3px 22px rgba(0,0,0,0.92), 0 1px 3px rgba(0,0,0,0.95); }}
</style>
<div id="root" data-composition-id="captions">
{cues}
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  window.__timelines["captions"] = tl;
</script>
</template>
</body>
</html>
"""

CUE = """  <div id="cue-{index}" class="clip cue" data-track-kind="captions"
       data-start="{start}" data-duration="{length}">{text}</div>"""


def scene_windows(
    cues: list[dict], count: int, total: float
) -> list[tuple[float, float]]:
    first: dict[int, float] = {}
    for cue in cues:
        first.setdefault(cue["scene"], float(cue["start"]))
    bounds = [0.0]
    for scene in range(2, count + 1):
        bounds.append(round(max(bounds[-1] + 0.5, first.get(scene, total)), 3))
    bounds.append(round(total, 3))
    return [(bounds[i], bounds[i + 1]) for i in range(count)]


def compose(
    root: Path,
    spec: ReelSpec,
    cues: list[dict],
    total: float,
    visuals: dict[int, list[str]],
    design: Design | None = None,
) -> dict[str, Path]:
    design = design or Design()
    tokens = {
        "bg": design.bg,
        "fg": design.fg,
        "accent": design.accent,
        "dim": design.dim,
        "line": design.line,
        "font_display": design.font_display,
        "font_mono": design.font_mono,
        "caption_bottom": design.caption_bottom,
        "caption_size": design.caption_size,
    }
    comps = root / "compositions"
    comps.mkdir(parents=True, exist_ok=True)
    slug = spec.slug
    windows = scene_windows(cues, len(spec.scenes), total)

    hosts, written = [], {}
    for index, (scene, (start, end)) in enumerate(zip(spec.scenes, windows), start=1):
        sid = f"s{index}"
        variant = (index - 1) % 5 + 1
        style = VARIANTS[variant]
        plates = visuals.get(index, [])
        plate = plates[0] if plates else "assets/visuals/fallback.svg"
        wave = ""
        for ref in plates[1:]:
            wave += f'  <img class="wave" src="{ref}" alt="" />\n'
        ghost_size, ghost_left = _ghost_box(
            style["numeral"], scene.label, style["ghost"]
        )
        path = comps / f"{sid}.html"
        path.write_text(
            SCENE.format(
                sid=sid,
                n=index,
                count=len(spec.scenes),
                variant=variant,
                kicker=html.escape(spec.kicker),
                overlay=html.escape(scene.overlay),
                label=html.escape(scene.label),
                h1size=style["size"],
                top=style["top"],
                right=style["right"],
                numeral=style["numeral"],
                ghostsize=ghost_size,
                ghostleft=ghost_left,
                ghosttop=style["ghosttop"],
                ghostdx=-70 if style["ghost"] == "left" else 70,
                glowx=520 if variant % 2 else 60,
                glowy=-320 if variant % 2 else 980,
                plate=plate,
                wave=wave,
                length=round(end - start, 3),
                **tokens,
            )
        )
        hosts.append(
            HOST.format(sid=sid, start=round(start, 3), length=round(end - start, 3))
        )
        written[sid] = path

    cue_html = []
    for number, cue in enumerate(cues, start=1):
        scene_spec = spec.scenes[int(cue["scene"]) - 1]
        if _plain(cue["text"]) == _plain(scene_spec.overlay):
            continue
        start = max(0.0, float(cue["start"]))
        end = min(float(total), max(start + 0.6, float(cue["end"])))
        cue_html.append(
            CUE.format(
                index=number,
                start=round(start, 3),
                length=round(end - start, 3),
                text=html.escape(cue["text"]),
            )
        )
    (comps / "captions.html").write_text(
        CAPTIONS.format(cues="\n".join(cue_html), **tokens)
    )

    index = root / "index.html"
    index.write_text(
        HEAD.format(
            title=html.escape(spec.title),
            cid=f"reel-{slug}",
            total=round(total, 3),
            hosts="\n".join(hosts),
            captions=CAPTION_HOST.format(total=round(total, 3)),
            audio=AUDIO.format(total=round(total, 3)),
            **tokens,
        )
    )
    written["index"] = index
    written["captions"] = comps / "captions.html"
    return written


def _plain(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace()).strip()


def _ghost_box(numeral: int, label: str, side: str) -> tuple[int, int]:
    """Size the ghost label so it fits the frame, then place it."""
    size = min(numeral, int(980 / (0.82 * max(len(label), 3))))
    width = int(0.82 * size * len(label))
    if side == "right":
        left = max(36, 1044 - width)
    elif side == "center":
        left = max(36, (1080 - width) // 2)
    else:
        left = 36
    return size, left
