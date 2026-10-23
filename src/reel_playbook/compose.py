"""Compose HyperFrames HTML from visuals, cues and the master take.

Audio is mounted once, last, as the master. Scene windows come from cue starts,
so picture follows voice instead of padding audio to fit picture.
"""

from __future__ import annotations

import html
from pathlib import Path

from .content import ReelSpec

SIZES = {1: (128, 470), 2: (104, 520), 3: (96, 540), 4: (92, 540), 5: (92, 540),
         6: (96, 540), 7: (100, 530), 8: (112, 510)}

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  html, body {{ margin:0; width:1080px; height:1920px; background:#0b0b0c; }}
  body {{ font-family:"Helvetica Neue", Arial, sans-serif; }}
  #root {{ position:relative; width:100%; height:100%; overflow:hidden;
          background: radial-gradient(120% 80% at 50% 0%, #17171a 0%, #0b0b0c 62%); }}
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
  #root {{ position:absolute; inset:0; color:#f2efe6; font-family:"Helvetica Neue", Arial, sans-serif; overflow:hidden; }}
  .plate {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }}
  .veil {{ position:absolute; inset:0;
          background: linear-gradient(180deg, rgba(11,11,12,0.30) 0%, rgba(11,11,12,0.72) 55%, rgba(11,11,12,0.94) 100%); }}
  .frame {{ position:absolute; inset:52px; border:1px solid rgba(242,239,230,0.13); }}
  .index {{ position:absolute; top:78px; right:82px; font-family:"Courier New",monospace;
           font-size:30px; letter-spacing:.16em; color:#8a867c; }}
  .kicker {{ position:absolute; top:96px; left:82px; font-family:"Courier New",monospace;
            font-size:30px; letter-spacing:.2em; color:#e0a33e; text-transform:uppercase; }}
  .body {{ position:absolute; left:82px; right:82px; top:{top}px; }}
  .rule {{ width:88px; height:6px; background:#e0a33e; margin-bottom:38px; }}
  h1 {{ margin:0; font-size:{size}px; line-height:.95; letter-spacing:-.03em; font-weight:600; }}
  .label {{ position:absolute; left:82px; bottom:124px; font-family:"Courier New",monospace;
           font-size:30px; letter-spacing:.14em; color:#8a867c; text-transform:uppercase; }}
  .foot {{ position:absolute; right:82px; bottom:124px; font-family:"Courier New",monospace;
          font-size:30px; letter-spacing:.1em; color:#8a867c; }}
  .progress {{ position:absolute; left:52px; right:52px; bottom:70px; height:2px;
              background:#e0a33e; transform-origin:left center; }}
  .wave {{ position:absolute; left:80px; right:80px; bottom:330px; width:920px;
          opacity:.55; mix-blend-mode:screen; }}
</style>
<div id="root" data-composition-id="{sid}">
  <img class="plate" src="{plate}" alt="" />
  <div class="veil"></div>
  <div class="frame" id="{sid}-frame"></div>
  <div class="index" id="{sid}-index">{n:02d} / {count:02d}</div>
  <div class="kicker" id="{sid}-kicker">{kicker}</div>
  <div class="body" id="{sid}-body">
    <div class="rule" id="{sid}-rule"></div>
    <h1 id="{sid}-title">{overlay}</h1>
  </div>
  <div class="label" id="{sid}-label">{label}</div>
  <div class="foot" id="{sid}-foot">the flying eyes</div>
  <div class="progress" id="{sid}-progress"></div>
{wave}
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  tl.fromTo("#{sid}-title", {{ y: 34 }}, {{ y: 0, duration: 0.7, ease: "power3.out" }}, 0);
  tl.fromTo("#{sid}-rule", {{ scaleX: 0, transformOrigin: "left center" }},
            {{ scaleX: 1, duration: 0.55, ease: "power2.out" }}, 0.08);
  tl.fromTo("#{sid}-kicker", {{ y: 14 }}, {{ y: 0, duration: 0.5, ease: "power3.out" }}, 0.12);
  tl.fromTo("#{sid}-label", {{ y: 12 }}, {{ y: 0, duration: 0.5, ease: "power3.out" }}, 0.2);
  tl.fromTo("#{sid}-plate", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {length}, ease: "none" }}, 0);
  tl.fromTo("#{sid}-progress", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {length}, ease: "none" }}, 0);
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
  #root {{ position:absolute; inset:0; font-family:"Helvetica Neue", Arial, sans-serif; color:#ffffff; }}
  .cue {{ position:absolute; left:60px; right:60px; bottom:210px; text-align:center;
         font-size:40px; line-height:1.24; font-weight:600; letter-spacing:-0.01em;
         text-shadow:0 2px 18px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.9); }}
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

CUE = """  <div class="cue" data-start="{start}" data-duration="{length}">{text}</div>"""


def scene_windows(cues: list[dict], count: int, total: float) -> list[tuple[float, float]]:
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
) -> dict[str, Path]:
    comps = root / "compositions"
    comps.mkdir(parents=True, exist_ok=True)
    slug = spec.slug
    windows = scene_windows(cues, len(spec.scenes), total)

    hosts, written = [], {}
    for index, (scene, (start, end)) in enumerate(zip(spec.scenes, windows), start=1):
        sid = f"s{index}"
        size, top = SIZES.get(index, (96, 540))
        plates = visuals.get(index, [])
        plate = plates[0] if plates else "assets/visuals/fallback.svg"
        wave = ""
        for ref in plates[1:]:
            wave += f'  <img class="wave" src="{ref}" alt="" />\n'
        path = comps / f"{sid}.html"
        path.write_text(
            SCENE.format(
                sid=sid, n=index, count=len(spec.scenes), kicker=spec.kicker,
                overlay=html.escape(scene.overlay), label=html.escape(scene.label),
                size=size, top=top, plate=plate, wave=wave,
                length=round(end - start, 3),
            )
        )
        hosts.append(
            HOST.format(sid=sid, start=round(start, 3), length=round(end - start, 3))
        )
        written[sid] = path

    cue_html = []
    for cue in cues:
        start = max(0.0, float(cue["start"]))
        end = min(float(total), max(start + 0.6, float(cue["end"])))
        cue_html.append(
            CUE.format(
                start=round(start, 3),
                length=round(end - start, 3),
                text=html.escape(cue["text"]),
            )
        )
    (comps / "captions.html").write_text(CAPTIONS.format(cues="\n".join(cue_html)))

    index = root / "index.html"
    index.write_text(
        HEAD.format(
            title=html.escape(spec.title),
            cid=f"reel-{slug}",
            total=round(total, 3),
            hosts="\n".join(hosts),
            captions=CAPTION_HOST.format(total=round(total, 3)),
            audio=AUDIO.format(total=round(total, 3)),
        )
    )
    written["index"] = index
    written["captions"] = comps / "captions.html"
    return written
