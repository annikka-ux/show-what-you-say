"""Word-synced reel graphics: every graphic lands on the exact word it shows, plus karaoke captions and a
Signature-look CTA end card. Builds a HyperFrames project you then render with finish.sh.

usage: python3 gen.py VIDEO WORDS.json BEATS BRAND [OUT_DIR]
  VIDEO       your tight-cut talking-head clip, 1080x1920 (any length)
  WORDS.json  word timings from transcribe.sh (whisper-cli JSON, one word per segment)
  BEATS       a beats file in this folder without .py, e.g. beats_example (one per video)
  BRAND       a key in brands.json (palette, fonts, logo, CTA)
  OUT_DIR     default hf-<BRAND>

How a video gets made: cut it tight, transcribe it, then write a beats file by reading the word times:
each beat starts on the word it illustrates and ends when the speaker moves on. Claude Code can write the
beats file for you from WORDS.json (see skills/reel/SKILL.md)."""
import json, os, shutil, subprocess, html, sys, importlib

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO, WORDS, BEATS, BRAND = sys.argv[1:5]
HF = os.path.abspath(sys.argv[5]) if len(sys.argv) > 5 else f'{HERE}/hf-{BRAND}'
_ALL = json.load(open(f'{HERE}/brands.json'))
if os.path.exists(f'{HERE}/my-brands.json'): _ALL.update(json.load(open(f'{HERE}/my-brands.json')))   # yours, from brand.py
if BRAND == 'default': BRAND = _ALL.get('_default', 'classic')   # the brand saved by brand.py
B = _ALL[BRAND]
# LAYOUT=low (default): cards below the face. LAYOUT=high: face sits low in the frame, so cards go above the
# head and captions under the chin. lookaway.py tells you which one your video needs.
LAYOUT = os.environ.get('LAYOUT', 'low')
IMAGES = []   # real logos / screenshots used by cover(), copied into the project
CTA_LEN = 4.2

def probe(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

BASE = round(probe(VIDEO), 2)          # where the speaker's clip ends
CTA_AT = round(BASE + 0.2, 2)          # end card starts just after the last word, music only
TOTAL = round(CTA_AT + CTA_LEN, 2)

# ---- words for captions -------------------------------------------------
d = json.load(open(WORDS))
W = [[x['offsets']['from'] / 1000, x['text'].strip()] for x in d['transcription'] if x['text'].strip()]
W = [[t, w.replace('"', '')] for t, w in W]
for a, b in B.get('fix_words', {}).items():      # whisper misspellings, e.g. a name
    W = [[t, w.replace(a, b)] for t, w in W]

groups, cur = [], []
for i, (t, w) in enumerate(W):
    cur.append((t, w))
    txt = ' '.join(x[1] for x in cur)
    nxt = W[i + 1][0] if i + 1 < len(W) else BASE
    if len(cur) >= 3 or len(txt) > 15 or w[-1] in '.,?!' or nxt - t > 0.7:
        groups.append(cur); cur = []
if cur: groups.append(cur)

def at(word, after=0.0):
    """Start time of the first word containing `word` (case-insensitive) at or after `after` seconds.
    Lets a beats file say at('order') instead of hard-coding 6.40, so it survives a re-transcribe."""
    for t, w in W:
        if t >= after and word.lower() in w.lower():
            return t
    raise SystemExit(f'beats: word {word!r} not found after {after}s')

# ---- beat helpers: (start, end, html, timeline js) -------------------------
els, tw = [], []
def clip(id, a, b, inner, z=20, extra=''):
    """A layer on screen from a to b seconds. z: 19-29 overlays, 30+ full-screen cutaways."""
    els.append(f'<div id="{id}" class="clip" data-start="{a:.2f}" data-duration="{b-a:.2f}" data-track-index="{z}" style="z-index:{z}"{extra}>{inner}</div>')
def T(s): tw.append(s)
def out(sel, b, d=0.25):
    T(f'tl.to("{sel}", {{opacity:0, scale:0.92, duration:{d}, ease:"power2.in"}}, {b-d-0.02:.2f});')
def pop(sel, t, d=0.38):
    T(f'tl.from("{sel}", {{opacity:0, scale:0.6, y:18, duration:{d}, ease:"back.out(1.8)"}}, {t:.2f});')
def esc(s): return html.escape(s)

# Ready-made beats. Times are seconds on the cut's clock (read them from WORDS.json).
def card(id, a, b, label, big, t_big, t_slash=None):
    """White card: small label, big word lands on t_big, optional slash through it on t_slash."""
    sl = '<div class="slashw"><div class="slash" id="%s_s"></div></div>' % id if t_slash else ''
    clip(id, a, b, f'<div class="card mid" id="{id}_c"><div class="lbl">{esc(label)}</div><div class="grade" id="{id}_g">{esc(big)}</div>{sl}</div>')
    T(f'tl.from("#{id}_c", {{opacity:0, scale:0.7, duration:0.35, ease:"back.out(1.6)"}}, {a+0.05:.2f});')
    T(f'tl.from("#{id}_g", {{scale:1.8, opacity:0, duration:0.3, ease:"power3.out"}}, {t_big:.2f});')
    if t_slash: T(f'tl.fromTo("#{id}_s", {{scaleX:0}}, {{scaleX:1, duration:0.3, ease:"power3.out"}}, {t_slash:.2f});')
    out(f'#{id}_c', b)

def old_vs_new(id, a, b, old, t_old, t_strike, new, t_new):
    """Two chips: the old idea appears, gets struck out, the new idea pops in gold."""
    clip(id, a, b, f'<div class="row mid"><div class="chip" id="{id}_a">{esc(old)}<span class="strike" id="{id}_s"></span></div><div class="chip gold" id="{id}_b">✦ {esc(new)}</div></div>')
    pop(f'#{id}_a', t_old); T(f'tl.fromTo("#{id}_s", {{scaleX:0}}, {{scaleX:1, duration:0.3, ease:"power3.out"}}, {t_strike:.2f});')
    T(f'tl.to("#{id}_a", {{opacity:0.45, duration:0.2}}, {t_strike+0.1:.2f});'); pop(f'#{id}_b', t_new)
    out(f'#{id} .row', b)

def tag(id, a, b, text, t, good=True):
    """Pill at the top: ✓ STRONG ANSWER / ✗ WEAK ANSWER."""
    clip(id, a, b, f'<div class="tag {"good" if good else "bad"}" id="{id}_t">{"✓" if good else "✗"} {esc(text)}</div>', 22)
    T(f'tl.from("#{id}_t", {{opacity:0, scale:0.6, duration:0.35, ease:"back.out(1.8)"}}, {t:.2f});'); out(f'#{id}_t', b)

def side_chips(id, a, b, items, struck=False):
    """Words popping beside the head on the second they are said. items: [(t, word, 'L'|'R', y_px)]."""
    for i, (t, w, side, y) in enumerate(items):
        x = '<span class="x">✗</span>' if struck else ''
        clip(f'{id}{i}', t - 0.05, b, f'<div class="fchip {side}" id="{id}c{i}" style="top:{y}px">“{esc(w)}”{x}</div>', 21 + i)
        pop(f'#{id}c{i}', t - 0.04, 0.3)
        if struck: T(f'tl.from("#{id}c{i} .x", {{opacity:0, scale:2.2, duration:0.2, ease:"power3.out"}}, {t+0.22:.2f});')
        out(f'#{id}c{i}', b, 0.2)

def checklist(id, a, b, lines):
    """White list that builds line by line. lines: [(t, mark, text)], mark like '✓', '!', '2', '→'."""
    rows = ''.join(f'<div class="li" id="{id}_{i}"><b>{esc(m)}</b>{esc(x)}</div>' for i, (t, m, x) in enumerate(lines))
    clip(id, a, b, f'<div class="list" id="{id}_l">{rows}</div>')
    T(f'tl.from("#{id}_l", {{opacity:0, y:30, duration:0.35, ease:"power3.out"}}, {a+0.05:.2f});')
    for i, (t, m, x) in enumerate(lines):
        T(f'tl.from("#{id}_{i}", {{opacity:0, x:-40, duration:0.32, ease:"power3.out"}}, {t-0.05:.2f});')
        T(f'tl.fromTo("#{id}_{i} b", {{scale:0}}, {{scale:1, duration:0.3, ease:"back.out(2)"}}, {t+0.05:.2f});')
    out(f'#{id}_l', b)

def point(id, a, b, n, title, of=3):
    """Numbered point badge + progress bar for 'three things' structures."""
    segs = ''.join(f'<div class="seg"><i id="{id}_p{k}" style="transform:scaleX({1 if k < n else 0})"></i></div>' for k in range(1, of + 1))
    clip(id, a, b, f'<div class="track">{segs}</div><div class="numrow" id="{id}_r"><div class="num">{n}</div><div class="ptl">{esc(title)}</div></div>', 19)
    T(f'tl.fromTo("#{id}_p{n}", {{scaleX:0}}, {{scaleX:1, duration:0.5, ease:"power2.inOut"}}, {a+0.05:.2f});')
    T(f'tl.from("#{id}_r", {{opacity:0, scale:0.7, duration:0.3, ease:"back.out(1.8)"}}, {a+0.05:.2f});')
    out(f'#{id}_r', b, 0.15)

def cutaway_message(id, a, b, who, words, word_times, screen_lines=('yoursite.com',), alert=None, t_alert=None):
    """Full-screen cutaway on a grid: a browser mock (optional red alert) and a chat bubble whose words appear as spoken."""
    q = ' '.join(f'<span class="qw">{esc(w)}</span>' for w in words.split())
    al = f'<div class="err" id="{id}_e">⚠ {esc(alert)}</div>' if alert else ''
    clip(id, a, b, f'''<div class="canvas" id="{id}_bg">
  <div class="browser" id="{id}_b"><div class="bar"><i></i><i></i><i></i><span>{esc(screen_lines[0])}</span></div>
    <div class="pg"><div class="ph"></div><div class="ph s"></div><div class="btn">Continue</div>{al}</div></div>
  <div class="msg" id="{id}_m"><div class="who">{esc(who)}</div><div class="txt">{q}</div></div></div>''', 30)
    T(f'tl.to("#{id}_bg", {{opacity:1, duration:0.18, ease:"power2.out"}}, {a:.2f});')
    T(f'tl.from("#{id}_b", {{opacity:0, y:60, scale:0.9, duration:0.4, ease:"back.out(1.4)"}}, {a+0.09:.2f});')
    if alert:
        T(f'tl.from("#{id}_e", {{opacity:0, scale:1.4, duration:0.25, ease:"power4.out"}}, {t_alert:.2f});')
        T(f'tl.fromTo("#{id}_b", {{rotation:0}}, {{rotation:-2.5, duration:0.06, yoyo:true, repeat:5, ease:"none"}}, {t_alert+0.02:.2f});')
    T(f'tl.from("#{id}_m", {{opacity:0, y:40, scale:0.85, duration:0.35, ease:"back.out(1.6)"}}, {word_times[0]-0.5:.2f});')
    for k, t in enumerate(word_times):
        T(f'tl.from("#{id}_m .qw:nth-child({k+1})", {{opacity:0, y:8, duration:0.15, ease:"power2.out"}}, {t:.2f});')
    T(f'tl.to("#{id}_bg", {{opacity:0, duration:0.15, ease:"power2.in"}}, {b-0.15:.2f});')

def big_number(id, a, b, lines, t_lines, number, t_number, caption):
    """Full-screen cutaway: '= same X' chips stack up, then a giant number and a payoff line."""
    chips = ''.join(f'<div class="chip big" id="{id}_c{k}">{esc(x)}</div>' for k, x in enumerate(lines))
    clip(id, a, b, f'<div class="canvas" id="{id}_bg"><div class="eq">{chips}<div class="three"><span class="bign" id="{id}_n">{esc(number)}</span><div class="bigc" id="{id}_t">{esc(caption)}</div></div></div></div>', 30)
    T(f'tl.to("#{id}_bg", {{opacity:1, duration:0.15}}, {a:.2f});')
    for k, t in enumerate(t_lines): pop(f'#{id}_c{k}', t)
    T(f'tl.from("#{id}_n", {{opacity:0, scale:0.3, duration:0.45, ease:"back.out(2)"}}, {t_number:.2f});')
    T(f'tl.from("#{id}_t", {{opacity:0, y:20, duration:0.3, ease:"power3.out"}}, {t_number+0.38:.2f});')
    T(f'tl.to("#{id}_bg", {{opacity:0, duration:0.15}}, {b-0.17:.2f});')

def cover(id, a, b, lines, times, image=None, t_image=None, payoff=None, t_payoff=None):
    """Full-screen cutaway on your brand background. Use it to show the REAL thing you name (a logo, an app,
    a screenshot: image='path/to/file.png') and to cover any moment you look away from the camera.
    lines/times: short phrases that pop in as you say them; payoff: one big accent word at t_payoff."""
    img = ''
    if image:
        IMAGES.append(os.path.abspath(os.path.expanduser(image)))
        img = f'<div class="shot" id="{id}_i"><img src="assets/img/{esc(os.path.basename(image))}" /></div>'
    chips = ''.join(f'<div class="chip big" id="{id}_c{k}">{esc(x)}</div>' for k, x in enumerate(lines))
    pay = f'<div class="bigc" id="{id}_p">{esc(payoff)}</div>' if payoff else ''
    clip(id, a, b, f'<div class="canvas" id="{id}_bg"><div class="cov">{img}{chips}{pay}</div></div>', 30)
    T(f'tl.to("#{id}_bg", {{opacity:1, duration:0.15}}, {a:.2f});')
    if image: T(f'tl.from("#{id}_i", {{opacity:0, y:50, scale:0.9, duration:0.4, ease:"back.out(1.5)"}}, {(t_image or a + 0.05):.2f});')
    for k, t in enumerate(times): pop(f'#{id}_c{k}', t)
    if payoff: T(f'tl.from("#{id}_p", {{opacity:0, y:24, rotationX:-70, duration:0.45, ease:"back.out(1.7)"}}, {t_payoff:.2f});')
    T(f'tl.to("#{id}_bg", {{opacity:0, duration:0.15}}, {b-0.17:.2f});')

def chat(id, a, b, them, t_them, me, t_me, who='Client'):
    """Two chat bubbles: their question, your answer."""
    clip(id, a, b, f'<div class="chat mid"><div class="msg sm" id="{id}_1"><div class="who">{esc(who)}</div><div class="txt">{esc(them)}</div></div><div class="msg sm me" id="{id}_2"><div class="txt">{esc(me)}</div></div></div>')
    T(f'tl.from("#{id}_1", {{opacity:0, y:30, scale:0.85, duration:0.35, ease:"back.out(1.6)"}}, {t_them:.2f});')
    T(f'tl.from("#{id}_2", {{opacity:0, y:30, scale:0.85, duration:0.35, ease:"back.out(1.6)"}}, {t_me:.2f});')
    out(f'#{id} .chat', b)

# ---- the video's own beats --------------------------------------------------
sys.path.insert(0, HERE)
importlib.import_module(BEATS).build(sys.modules[__name__])

# ---- CTA end card (music only): 3D logo card, rings, sparkles, URL pill ----
C = B['cta']
spark = '<svg viewBox="0 0 100 100"><path d="M50 0 C54 38 62 46 100 50 C62 54 54 62 50 100 C46 62 38 54 0 50 C38 46 46 38 50 0Z"/></svg>'
clip('cta', CTA_AT, TOTAL, f'''<div class="canvas" id="ctabg">
  <div class="ring" id="r1"></div><div class="ring r2" id="r2"></div>
  <div class="sp" id="sp1" style="left:150px;top:380px">{spark}</div><div class="sp sm2" id="sp2" style="left:860px;top:520px">{spark}</div>
  <div class="sp sm2" id="sp3" style="left:190px;top:1150px">{spark}</div>
  <div class="persp"><div class="lcard" id="lc"><img src="assets/img/{os.path.basename(B['logo'])}" /></div></div>
  <div class="ctx">
    <div class="eye" id="ce">{esc(C['eyebrow'])}</div>
    <div class="ttl" id="ct">{esc(C['title'])}</div>
    <div class="det" id="cd">{esc(C['detail'])}</div>
    <div class="url" id="cu">{esc(C['url'])} →</div>
    <div class="fc" id="cf">{esc(C.get('footnote', 'Link in the first comment'))}</div>
  </div></div>''', 50)
a = CTA_AT
T(f'tl.to("#ctabg", {{opacity:1, duration:0.2, ease:"power2.out"}}, {a:.2f});')
T(f'tl.from("#lc", {{rotationY:-75, rotationX:12, opacity:0, scale:0.8, duration:0.7, ease:"power3.out"}}, {a+0.1:.2f});')
T(f'tl.to("#lc", {{rotationY:8, duration:{CTA_LEN-0.8:.2f}, ease:"sine.inOut"}}, {a+0.8:.2f});')
T(f'tl.from("#r1", {{scale:0.4, opacity:0, duration:0.6, ease:"power3.out"}}, {a+0.05:.2f}); tl.to("#r1", {{rotation:90, duration:{CTA_LEN:.2f}, ease:"none"}}, {a:.2f});')
T(f'tl.from("#r2", {{scale:0.4, opacity:0, duration:0.6, ease:"power3.out"}}, {a+0.15:.2f}); tl.to("#r2", {{rotation:-70, duration:{CTA_LEN:.2f}, ease:"none"}}, {a:.2f});')
for i in (1, 2, 3):
    T(f'tl.from("#sp{i}", {{scale:0, opacity:0, duration:0.4, ease:"back.out(2.5)"}}, {a+0.3+0.15*i:.2f}); tl.to("#sp{i}", {{rotation:{90 if i % 2 else -90}, duration:{CTA_LEN-0.4:.2f}, ease:"none"}}, {a+0.4:.2f});')
T(f'tl.from("#ce", {{opacity:0, y:16, scaleX:1.25, duration:0.4, ease:"power3.out"}}, {a+0.45:.2f});')
T(f'tl.from("#ct", {{opacity:0, y:30, rotationX:-70, duration:0.5, ease:"back.out(1.6)"}}, {a+0.65:.2f});')
T(f'tl.from("#cd", {{opacity:0, y:16, duration:0.35, ease:"power3.out"}}, {a+0.95:.2f});')
T(f'tl.from("#cu", {{opacity:0, scale:0.6, duration:0.4, ease:"back.out(2)"}}, {a+1.2:.2f}); tl.to("#cu", {{scale:1.06, duration:0.3, yoyo:true, repeat:1, ease:"sine.inOut"}}, {a+2.1:.2f});')
T(f'tl.from("#cf", {{opacity:0, duration:0.3}}, {a+1.5:.2f});')

# ---- karaoke captions: current word bright, rest dim ------------------------
cap_els = []
for gi, g in enumerate(groups):
    a = max(0.1, g[0][0] - 0.05)
    b = groups[gi + 1][0][0] - 0.05 if gi + 1 < len(groups) else BASE
    b = min(b, g[-1][0] + 1.1)
    spans = ''.join(f'<span class="cw" id="cw{gi}_{j}">{esc(w)}</span> ' for j, (t, w) in enumerate(g))
    cap_els.append(f'<div id="cg{gi}" class="clip cap" data-start="{a:.2f}" data-duration="{b-a:.2f}" data-track-index="40" style="z-index:40"><div class="capin">{spans.strip()}</div></div>')
    for j, (t, w) in enumerate(g):
        T(f'tl.to("#cw{gi}_{j}", {{color:"var(--bg)", duration:0.08}}, {t:.2f});')

def rgb(h): h = h.lstrip('#'); return ','.join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))
HIGH_CSS = '.mid { top:345px; } .list { top:345px; } .msg { top:345px; } .capin { top:1400px; }' if LAYOUT == 'high' else ''
P = B['palette']
F = B.get('fonts', {})
HEAD, SERIF = F.get('head', 'Montserrat'), F.get('accent', 'Cormorant')
ACC_STYLE = 'italic' if SERIF == 'Cormorant' else 'normal'
page = f'''<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face {{ font-family:"Public Sans"; src:url("assets/fonts/PublicSans-900.ttf"); font-weight:800 900; }}
@font-face {{ font-family:"Cormorant"; font-style:italic; src:url("assets/fonts/CormorantGaramond-Italic-VariableFont_wght.ttf"); font-weight:300 700; }}
@font-face {{ font-family:"Montserrat"; src:url("assets/fonts/Montserrat-VariableFont_wght.ttf"); font-weight:100 900; }}
:root {{ --primary:{P['primary']}; --accent:{P['accent']}; --bg:{P['bg']}; --ink:{P['ink']}; --red:{P.get('red', '#b5544a')};
  --primary-rgb:{rgb(P['primary'])}; --accent-rgb:{rgb(P['accent'])}; --bg-rgb:{rgb(P['bg'])}; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; background:#000; font-family:"{HEAD}"; }}
#root {{ position:relative; width:1080px; height:1920px; }}
#base {{ position:absolute; inset:0; width:1080px; height:1920px; object-fit:cover; }}
.clip {{ position:absolute; left:0; top:0; width:1080px; height:1920px; pointer-events:none; }}
.mid {{ position:absolute; left:0; right:0; margin:0 auto; top:960px; }}
.card {{ width:420px; height:250px; background:#fff; border-radius:34px; box-shadow:0 18px 50px rgba(0,0,0,.28); text-align:center; }}
.lbl {{ font-weight:800; font-size:30px; letter-spacing:.14em; color:var(--primary); padding-top:34px; }}
.grade {{ font-family:"{SERIF}"; font-style:{ACC_STYLE}; font-weight:700; font-size:140px; line-height:150px; color:var(--red); }}
.slashw {{ position:absolute; left:30px; right:30px; top:128px; height:14px; transform:rotate(-12deg); }}
.slash {{ width:100%; height:14px; background:var(--primary); border-radius:7px; transform-origin:0 50%; }}
.row {{ display:flex; justify-content:center; gap:22px; }}
.chip {{ position:relative; display:inline-block; background:#fff; color:var(--primary); font-weight:800; font-size:44px; padding:24px 36px; border-radius:60px; box-shadow:0 14px 40px rgba(0,0,0,.25); white-space:nowrap; }}
.chip.gold {{ background:var(--accent); color:var(--primary); font-family:"{SERIF}"; font-style:{ACC_STYLE}; font-weight:700; font-size:62px; padding:14px 40px; }}
.strike {{ position:absolute; left:22px; right:22px; top:50%; height:8px; margin-top:-4px; background:var(--red); border-radius:4px; transform-origin:0 50%; }}
.canvas {{ position:absolute; inset:0; opacity:0; background-color:var(--bg);
  background-image:linear-gradient(rgba(var(--primary-rgb),.07) 2px, transparent 2px), linear-gradient(90deg, rgba(var(--primary-rgb),.07) 2px, transparent 2px); background-size:60px 60px; }}
.browser {{ position:absolute; left:120px; top:420px; width:840px; height:520px; background:#fff; border-radius:30px; box-shadow:0 24px 60px rgba(var(--primary-rgb),.22); overflow:hidden; }}
.bar {{ height:64px; background:#ece6d9; display:flex; align-items:center; gap:12px; padding-left:26px; }}
.bar i {{ width:18px; height:18px; border-radius:9px; background:#cfc6b4; }}
.bar span {{ margin-left:20px; font-size:26px; font-weight:600; color:#7b8a89; }}
.pg {{ padding:44px 60px; }}
.ph {{ height:34px; width:560px; background:#ece6d9; border-radius:17px; margin-bottom:22px; }} .ph.s {{ width:380px; }}
.btn {{ margin-top:30px; width:300px; height:84px; border-radius:42px; background:var(--primary); color:var(--bg); font-weight:800; font-size:34px; line-height:84px; text-align:center; }}
.err {{ position:absolute; left:60px; right:60px; bottom:46px; height:96px; border-radius:24px; background:#f6dcd7; color:var(--red); font-weight:800; font-size:40px; line-height:96px; text-align:center; }}
.msg {{ position:absolute; left:120px; top:1010px; width:840px; background:var(--primary); color:var(--bg); border-radius:36px 36px 36px 8px; padding:30px 40px 38px; box-shadow:0 20px 50px rgba(var(--primary-rgb),.3); }}
.who {{ font-size:26px; font-weight:700; letter-spacing:.1em; color:var(--accent); text-transform:uppercase; margin-bottom:10px; }}
.txt {{ font-size:46px; font-weight:700; line-height:1.25; }}
.qw {{ display:inline-block; }}
.tag {{ position:absolute; top:205px; left:0; right:0; margin:0 auto; width:max-content; font-weight:900; font-size:40px; letter-spacing:.08em; padding:20px 40px; border-radius:50px; box-shadow:0 12px 34px rgba(0,0,0,.25); }}
.tag.bad {{ background:#fff; color:var(--red); }} .tag.good {{ background:var(--accent); color:var(--primary); }}
.fchip {{ position:absolute; background:#fff; color:var(--red); font-weight:800; font-size:36px; padding:14px 28px; border-radius:40px; box-shadow:0 12px 30px rgba(0,0,0,.25); white-space:nowrap; }}
.fchip.L {{ left:34px; }} .fchip.R {{ right:34px; }}
.fchip .x {{ display:inline-block; margin-left:12px; color:var(--primary); font-weight:900; }}
.list {{ position:absolute; left:110px; top:940px; width:860px; background:#fff; border-radius:34px; padding:18px 34px; box-shadow:0 20px 50px rgba(0,0,0,.28); }}
.li {{ display:flex; align-items:center; gap:22px; font-size:34px; font-weight:700; color:var(--ink); height:52px; }}
.li b {{ flex:none; width:48px; height:48px; border-radius:24px; background:var(--primary); color:var(--accent); font-size:28px; font-weight:900; line-height:48px; text-align:center; }}
.eq {{ position:absolute; top:520px; left:0; right:0; text-align:center; }}
.chip.big {{ font-size:54px; display:block; width:max-content; margin:0 auto 36px; }}
.three {{ margin-top:30px; }}
.bign {{ display:inline-block; font-weight:900; font-size:300px; line-height:300px; color:var(--accent); }}
.bigc {{ font-family:"{SERIF}"; font-style:{ACC_STYLE}; font-weight:700; font-size:88px; color:var(--primary); }}
.track {{ position:absolute; top:180px; left:0; right:0; margin:0 auto; width:300px; display:flex; gap:10px; }}
.seg {{ flex:1; height:10px; border-radius:5px; background:rgba(var(--primary-rgb),.6); border:2px solid rgba(var(--bg-rgb),.8); overflow:hidden; }}
.seg i {{ display:block; width:100%; height:100%; background:var(--accent); transform-origin:0 50%; }}
.numrow {{ position:absolute; top:225px; left:0; right:0; display:flex; justify-content:center; align-items:center; gap:16px; }}
.num {{ width:92px; height:92px; border-radius:46px; background:var(--primary); color:var(--accent); border:4px solid var(--accent); font-weight:900; font-size:52px; line-height:84px; text-align:center; }}
.ptl {{ background:var(--accent); color:var(--primary); font-weight:900; font-size:40px; letter-spacing:.04em; padding:20px 36px; border-radius:46px; }}
.chat {{ width:860px; height:300px; }}
.msg.sm {{ position:absolute; top:0; left:0; width:640px; }}
.msg.sm .txt {{ font-size:44px; }}
.msg.me {{ top:170px; left:auto; right:0; width:auto; background:var(--accent); color:var(--primary); border-radius:36px 36px 8px 36px; padding:26px 40px; }}
.ring {{ position:absolute; left:290px; top:330px; width:500px; height:500px; border-radius:50%; border:3px dashed rgba(var(--accent-rgb),.55); }}
.ring.r2 {{ left:240px; top:280px; width:600px; height:600px; border:2px solid rgba(var(--primary-rgb),.12); }}
.sp {{ position:absolute; width:70px; height:70px; }} .sp.sm2 {{ width:44px; height:44px; }}
.sp svg {{ width:100%; height:100%; fill:var(--accent); }}
.persp {{ position:absolute; left:0; right:0; top:400px; height:360px; perspective:1400px; }}
.lcard {{ margin:0 auto; width:360px; height:360px; border-radius:48px; background:#fff; box-shadow:0 30px 70px rgba(var(--primary-rgb),.25); display:flex; align-items:center; justify-content:center; }}
.lcard img {{ max-width:270px; max-height:270px; }}
.ctx {{ position:absolute; left:0; right:0; top:860px; text-align:center; perspective:1200px; }}
.eye {{ font-weight:800; font-size:32px; letter-spacing:.2em; color:var(--primary); opacity:.75; }}
.ttl {{ font-family:"{SERIF}"; font-style:{ACC_STYLE}; font-weight:700; font-size:118px; line-height:1.05; color:var(--accent); margin-top:14px; }}
.det {{ font-weight:700; font-size:36px; color:var(--ink); margin-top:22px; }}
.url {{ display:inline-block; margin-top:40px; background:var(--primary); color:var(--bg); font-weight:800; font-size:42px; padding:22px 44px; border-radius:60px; box-shadow:0 16px 40px rgba(var(--primary-rgb),.3); }}
.fc {{ font-weight:600; font-size:30px; color:var(--ink); opacity:.7; margin-top:26px; }}
.cap {{ text-align:center; }}
.capin {{ position:absolute; top:1252px; left:0; right:0; margin:0 auto; width:max-content; max-width:960px; background:rgba(var(--primary-rgb),.92); border-radius:22px; padding:10px 28px 14px; font-weight:800; font-size:54px; line-height:1.2; }}
.cw {{ color:rgba(var(--bg-rgb),.45); }}
.cov {{ position:absolute; top:330px; left:0; right:0; text-align:center; }}
.shot {{ width:880px; margin:0 auto 46px; background:#fff; border-radius:30px; overflow:hidden; box-shadow:0 24px 60px rgba(var(--primary-rgb),.25); }}
.shot img {{ display:block; width:100%; max-height:760px; object-fit:contain; background:#fff; }}
{HIGH_CSS}
{B.get('extra_css', '')}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL:.2f}" data-width="1080" data-height="1920">
<video id="base" class="clip" src="assets/base.mp4" muted playsinline data-start="0" data-duration="{TOTAL:.2f}" data-track-index="0"></video>
{chr(10).join(els)}
{chr(10).join(cap_els)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(tw)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
'''

if not os.path.isdir(HF):
    shutil.copytree(f'{HERE}/template', HF)
os.makedirs(f'{HF}/assets/img', exist_ok=True)
shutil.copy(os.path.join(HERE, B['logo']), f'{HF}/assets/img/')
for im in IMAGES: shutil.copy(im, f'{HF}/assets/img/')
bm = f'{HF}/assets/base.mp4'
# the speaker's clip, silent, frozen on its last frame under the end card (finish.sh adds the voice back)
if not os.path.exists(bm) or os.path.getmtime(bm) < os.path.getmtime(VIDEO):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', VIDEO, '-vf', f'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,tpad=stop_mode=clone:stop_duration={TOTAL - BASE + 0.2:.2f}',
                    '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-g', '30', '-pix_fmt', 'yuv420p', bm], check=True)
open(f'{HF}/index.html', 'w').write(page)
print('captions', len(groups), 'layers', len(els), 'total', TOTAL, 's ->', HF)
