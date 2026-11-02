"""Remix an edit: rebuild a reference video's rhythm (its cuts, beats, camera moves and transitions) with your
own photos or clips, in the Signature look. Works from a plan written by analyze.py, or from a ready-made preset.

usage: python3 remix.py PLAN BRAND SUBJECT [SUBJECT ...] [options]
  PLAN      a plan from analyze.py (my-ref.plan.json), or a preset name from presets/ (hype, cinematic, reveal, story)
  BRAND     a key in ../synced/brands.json (palette, fonts, logo, CTA)
  SUBJECT   your photos (jpg, png, heic) or clips (mp4, mov); they take turns across the shots.
            A PNG with a transparent background (a product, a cutout of you) floats on the brand stage
            instead of filling the frame.
options:
  --hook "Busy."       big word on screen at frame 0, struck out on the second beat (the old way)
  --lead "Now"         small line above the payoff word
  --payoff "Booked."   the end scene: shape morph into the brand colour, the word flips in letter by letter,
                       rings, sparkles and your last photo on a 3D card
  --lines "A|B|C"      short lines, one per shot after the hook, each landing on its shot's first beat
  --music FILE         the track you will finish with: its beats drive the punches, and every cut within
                       0.25 s of a beat snaps onto it (pass the same file to finish.sh)
  --no-cta             leave off the end card (on by default, from brands.json)
  --brands FILE        your own brands file instead of ../synced/brands.json (keep it outside the kit;
                       its logo path is relative to that file)
  --out DIR            default hf-remix-<BRAND>
Then render with: ./finish.sh DIR OUT.mp4 [MUSIC.mp3 or the reference itself, if you have the rights]"""
import html, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
args = sys.argv[1:]
def opt(name, default=None, flag=False):
    if name not in args: return default
    i = args.index(name)
    if flag: del args[i]; return True
    v = args[i + 1]; del args[i:i + 2]; return v
HOOK, LEAD, PAYOFF = opt('--hook'), opt('--lead'), opt('--payoff')
LINES = [x.strip() for x in opt('--lines', '').split('|') if x.strip()]
NO_CTA = opt('--no-cta', flag=True)
OUTDIR, MUSIC = opt('--out'), opt('--music')
BRANDS = os.path.abspath(opt('--brands', f'{KIT}/synced/brands.json'))
if len(args) < 3: raise SystemExit(__doc__)
PLAN, BRAND, SUBJECTS = args[0], args[1], [os.path.abspath(s) for s in args[2:]]
HF = os.path.abspath(OUTDIR or f'{HERE}/hf-remix-{BRAND}')
_ALL = json.load(open(BRANDS))
_MINE = os.path.join(os.path.dirname(BRANDS), 'my-brands.json')   # your brand, saved by synced/brand.py
if os.path.exists(_MINE): _ALL.update(json.load(open(_MINE)))
if BRAND == 'default': BRAND = _ALL.get('_default', 'classic')
B = _ALL[BRAND]
LOGO = os.path.join(os.path.dirname(BRANDS), B['logo'])
P, F = B['palette'], B.get('fonts', {})
HEAD, SERIF = F.get('head', 'Montserrat'), F.get('accent', 'Cormorant')
ACC_STYLE = 'italic' if SERIF == 'Cormorant' else 'normal'
CTA_LEN, END_MIN = 4.2, 2.6
VIDEO_EXT = ('.mp4', '.mov', '.m4v', '.webm')

plan_file = PLAN if os.path.exists(PLAN) else f'{HERE}/presets/{PLAN}.json'
if not os.path.exists(plan_file): raise SystemExit(f'no plan or preset called {PLAN!r} (presets: ' +
    ', '.join(sorted(f[:-5] for f in os.listdir(f'{HERE}/presets') if f.endswith('.json'))) + ')')
plan = json.load(open(plan_file))
DUR = plan['duration']
beats = plan.get('beats') or []
shots = [dict(s) for s in plan['shots']]

if MUSIC:     # your track sets the beat: punches follow it, and near-miss cuts snap onto it
    mp = os.path.join(os.path.dirname(os.path.abspath(HF)), '.music.plan.json')
    os.makedirs(os.path.dirname(mp), exist_ok=True)
    subprocess.run([sys.executable, f'{HERE}/analyze.py', os.path.abspath(MUSIC), mp], check=True, capture_output=True)
    m = json.load(open(mp)); os.remove(mp)
    beats = [t for t in m['beats'] if t < DUR]
    plan['bpm'] = m['bpm']
    snapped = 0
    for i in range(1, len(shots)):
        c = shots[i]['start']
        near = min(beats, key=lambda t: abs(t - c), default=c)
        if 0 < abs(near - c) <= 0.25 and shots[i - 1]['start'] + 0.3 < near < shots[i]['end'] - 0.3:
            shots[i - 1]['end'] = shots[i]['start'] = round(near, 3); snapped += 1
    print(f'music: {m["bpm"]} BPM, {snapped} of {len(shots) - 1} cuts snapped to its beats')

# the payoff scene needs room: fold the last shots into one end scene of at least END_MIN seconds
end_scene = None
if PAYOFF:
    while len(shots) > 1 and shots[-1]['end'] - shots[-1]['start'] < END_MIN:
        shots[-2]['end'] = shots[-1]['end']; shots.pop()
    end_scene = shots.pop()
    if not shots: raise SystemExit('the plan is too short for a payoff scene; drop --payoff or use a longer reference')
CTA_AT = DUR
TOTAL = round(DUR + (0 if NO_CTA else CTA_LEN), 2)

def esc(s): return html.escape(s)
def run(cmd): subprocess.run(cmd, check=True, capture_output=True)
def probe_json(f, entries):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', entries, '-of', 'json', f], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)

# ---- subjects: photos resized once, clips cut per shot later ------------------------------------
if not os.path.isdir(HF): shutil.copytree(f'{KIT}/synced/template', HF)
A = f'{HF}/assets/img'; os.makedirs(A, exist_ok=True)
for f in os.listdir(A):
    if f.startswith(('sub', 'shot')): os.remove(f'{A}/{f}')
shutil.copy(LOGO, A)
subs = []
for i, s in enumerate(SUBJECTS):
    if not os.path.exists(s): raise SystemExit(f'not found: {s}')
    ext = os.path.splitext(s)[1].lower()
    if ext in VIDEO_EXT:
        subs.append({'kind': 'video', 'src': s, 'len': float(probe_json(s, 'format=duration')['format']['duration']), 'used': 0.0}); continue
    src = s
    if ext in ('.heic', '.heif'):          # iPhone photos: macOS converts them for free
        src = f'{A}/sub{i}-in.jpg'; run(['sips', '-s', 'format', 'jpeg', s, '--out', src])
    pix = probe_json(src, 'stream=pix_fmt')['streams'][0].get('pix_fmt', '')
    cut = ext == '.png' and ('a' in pix.replace('yuv', ''))       # rgba, ya8, pal8 with alpha...
    dst = f'{A}/sub{i}.{"png" if cut else "jpg"}'
    run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', "scale='min(1600,iw)':-2", '-frames:v', '1'] + ([] if cut else ['-q:v', '3']) + [dst])
    subs.append({'kind': 'cutout' if cut else 'photo', 'src': os.path.basename(dst), 'name': os.path.basename(s)})

# faces: the Mac's own Vision framework finds them (faces.swift), so a 9:16 crop keeps the face in frame,
# pushes zoom toward it and words stay off it. No swift (no Xcode tools)? Photos are centred instead.
FACE = {}
photos = [x for x in subs if x['kind'] == 'photo']
if photos and shutil.which('swift'):
    r = subprocess.run(['swift', f'{HERE}/faces.swift'] + [f'{A}/{x["src"]}' for x in photos], capture_output=True, text=True)
    for line, x in zip(r.stdout.splitlines(), photos):
        j = json.loads(line)
        if not j['faces']: continue
        f = max(j['faces'], key=lambda b: b[2] * b[3])
        FACE[x['src']] = (f, j['w'], j['h'])
        if f[0] < 0.01 or f[1] < 0.01 or f[0] + f[2] > 0.99 or f[1] + f[3] > 0.99:
            print(f'warning: {x["name"]}: the face touches the edge of the photo, so it will look cut off. Pick another photo.')
elif photos:
    print('(swift not found: photos are centred, not framed on faces. xcode-select --install adds it, free.)')

def framing(sub):
    """Where the face lands once the photo fills 1080x1920: object-position, zoom origin, face top/bottom."""
    if sub['kind'] == 'cutout': return {'y0': 520, 'y1': 1290}
    if sub['src'] not in FACE: return None
    (fx, fy, fw, fh), iw, ih = FACE[sub['src']]
    sc = max(1080 / iw, 1920 / ih); sw, sh = iw * sc, ih * sc
    cx, cy = (fx + fw / 2) * sw, (fy + fh / 2) * sh
    px = min(1, max(0, (cx - 540) / (sw - 1080))) if sw > 1081 else 0.5
    py = min(1, max(0, (cy - 860) / (sh - 1920))) if sh > 1921 else 0.5      # face a little above the middle
    ox, oy = (sw - 1080) * px, (sh - 1920) * py
    cx, cy, y0, y1 = cx - ox, cy - oy, fy * sh - oy, (fy + fh) * sh - oy
    z = 1.26                                                                    # the biggest a move zooms in
    return {'pos': f'{px * 100:.1f}% {py * 100:.1f}%', 'cx': cx, 'cy': cy, 'y0': cy + (y0 - cy) * z - 50, 'y1': cy + (y1 - cy) * z + 50}

SLOTS = {'top': (230, 470), 'mid': (740, 1000), 'low': (1290, 1440)}
def slot(bands, prefs):
    """First text slot in prefs that stays clear of every face band; else the one that overlaps least."""
    def hit(p): return sum(max(0, min(SLOTS[p][1], b['y1']) - max(SLOTS[p][0], b['y0'])) for b in bands if b)
    return next((p for p in prefs if hit(p) == 0), min(prefs, key=hit))

# ---- timeline pieces ----------------------------------------------------------------------------
els, tw = [], []
def T(s): tw.append(s)
spark = '<svg viewBox="0 0 100 100"><path d="M50 0 C54 38 62 46 100 50 C62 54 54 62 50 100 C46 62 38 54 0 50 C38 46 46 38 50 0Z"/></svg>'
def beats_in(a, b): return [t for t in beats if a + 0.08 < t < b - 0.08]

MOVES = {   # (from, to) for the .cam layer, scaled by the shot's strength
    'push_in':   ({'scale': 1.06}, {'scale': 1.24}),
    'pull_out':  ({'scale': 1.24}, {'scale': 1.06}),
    'pan_left':  ({'scale': 1.2, 'x': -70}, {'scale': 1.2, 'x': 70}),      # camera moves left, picture slides right
    'pan_right': ({'scale': 1.2, 'x': 70}, {'scale': 1.2, 'x': -70}),
    'tilt_up':   ({'scale': 1.2, 'y': -90}, {'scale': 1.2, 'y': 90}),
    'tilt_down': ({'scale': 1.2, 'y': 90}, {'scale': 1.2, 'y': -90}),
    'orbit':     ({'scale': 1.14, 'rotationY': -9}, {'scale': 1.14, 'rotationY': 9}),
    'still':     ({'scale': 1.06}, {'scale': 1.1}),
    'handheld':  ({'scale': 1.12}, {'scale': 1.14}),
}
def js(d): return '{' + ', '.join(f'{k}:{v}' for k, v in d.items()) + '}'
def scaled(d, k):
    return {key: round(1 + (v - 1) * k, 3) if key == 'scale' else round(v * k, 2) for key, v in d.items()}

prev_cam = None
for n, s in enumerate(shots):
    a, b = s['start'], s['end']; d = b - a
    WHIP = 0.18
    nxt_whip = n + 1 < len(shots) and shots[n + 1].get('arrive') == 'whip'
    d_show = d + (WHIP if nxt_whip else 0)        # a whip slides this shot out while the next one slides in
    sub = subs[n % len(subs)]
    if len(subs) > 1 and n and subs[(n - 1) % len(subs)] is sub: sub = subs[(n + 1) % len(subs)]
    wid, cam, pun = f'w{n}', f'c{n}', f'p{n}'
    fr = framing(sub); s['band'] = fr
    pos = f' style="object-position:{fr["pos"]}"' if fr and 'pos' in fr else ''
    origin = f' style="transform-origin:{fr["cx"]:.0f}px {fr["cy"]:.0f}px"' if fr and 'cx' in fr else ''
    if sub['kind'] == 'video':          # each shot takes the next stretch of the clip, looping
        st = sub['used'] if sub['used'] + d < sub['len'] else 0.0
        sub['used'] = st + d
        media = f'<video id="v{n}" class="clip sub" src="{esc(sub["src"])}" muted playsinline data-start="{a:.2f}" data-duration="{d_show:.2f}" data-media-start="{st:.2f}" data-track-index="{1 + n % 2}"></video>'
    elif sub['kind'] == 'cutout':
        media = f'''<div id="st{n}" class="clip stage" data-start="{a:.2f}" data-duration="{d_show:.2f}" data-track-index="{1 + n % 2}">
  <div class="sring"></div><div class="sring r2"></div><div class="sp" style="left:150px;top:520px">{spark}</div><div class="sp sm2" style="left:860px;top:1180px">{spark}</div>
  <img class="cutimg" src="assets/img/{sub["src"]}" /></div>'''
    else:
        media = f'<img id="i{n}" class="clip sub"{pos} src="assets/img/{sub["src"]}" data-start="{a:.2f}" data-duration="{d_show:.2f}" data-track-index="{1 + n % 2}" />'
    els.append(f'<div class="layer" id="{wid}" style="z-index:{1 + n % 2}"><div class="layer cam" id="{cam}"{origin}><div class="layer" id="{pun}">{media}</div></div></div>')
    k = 0.5 + 0.5 * s.get('strength', 0.5)
    mv = s.get('move', 'still')
    f0, f1 = MOVES.get(mv, MOVES['still'])
    T(f'tl.fromTo("#{cam}", {js(scaled(f0, k))}, {{...{js(scaled(f1, k))}, duration:{d:.2f}, ease:"none"}}, {a:.2f});')
    if mv == 'handheld':
        T(f'tl.to("#{pun}", {{x:7, y:-5, rotation:0.5, duration:0.11, yoyo:true, repeat:{max(1, int(d / 0.11) - 1)}, ease:"sine.inOut"}}, {a:.2f});')
    # every beat inside the shot: a small punch, harder on energetic shots
    hit = 1.025 + 0.03 * min(1, s.get('energy', 0.05) * 6)
    for t in beats_in(a, b):
        T(f'tl.fromTo("#{pun}", {{scale:{hit:.3f}}}, {{scale:1, duration:0.2, ease:"power2.out", immediateRender:false}}, {t:.2f});')
    # how the shot arrives
    arr = s.get('arrive', 'cut') if n else 'cut'
    if arr == 'flash':
        T(f'tl.fromTo("#fx", {{opacity:0.92}}, {{opacity:0, duration:0.2, ease:"power2.out", immediateRender:false}}, {a:.2f});')
    elif arr == 'dip':
        T(f'tl.fromTo("#dip", {{opacity:0}}, {{opacity:1, duration:0.16, ease:"power2.in", immediateRender:false}}, {max(0, a - 0.16):.2f});')
        T(f'tl.fromTo("#dip", {{opacity:1}}, {{opacity:0, duration:0.24, ease:"power2.out", immediateRender:false}}, {a:.2f});')
    elif arr == 'whip' and prev_cam:
        T(f'tl.to("#{prev_cam[0]}", {{x:-1080, duration:{WHIP}, ease:"power2.inOut"}}, {a:.2f});')
        T(f'tl.fromTo("#{wid}", {{x:1080}}, {{x:0, duration:{WHIP}, ease:"power2.inOut", immediateRender:false}}, {a:.2f});')
    elif arr == 'zoom':
        T(f'tl.fromTo("#{wid}", {{scale:1.5}}, {{scale:1, duration:0.26, ease:"expo.out", immediateRender:false}}, {a:.2f});')
    elif arr == 'morph':
        mid = f'm{n}'
        els.append(f'<div id="{mid}h" class="clip" data-start="{max(0, a - 0.55):.2f}" data-duration="0.75" data-track-index="9" style="z-index:9"><div class="morph" id="{mid}"></div></div>')
        T(f'tl.fromTo("#{mid}", {{scale:0, rotation:0, borderRadius:100}}, {{scale:1, duration:0.2, ease:"back.out(2)"}}, {max(0, a - 0.55):.2f});')
        T(f'tl.to("#{mid}", {{borderRadius:24, rotation:45, scale:14, duration:0.35, ease:"expo.in"}}, {max(0, a - 0.35):.2f});')
        T(f'tl.to("#{mid}", {{opacity:0, duration:0.2}}, {a:.2f});')
    prev_cam = (wid, cam)

# ---- words on screen ------------------------------------------------------------------------------
if HOOK:
    h_end = min(shots[0]['end'] if len(shots) == 1 else shots[min(1, len(shots) - 1)]['end'], 3.0)
    h_end = max(h_end, min(2.2, DUR))
    b2 = next((t for t in beats if t > 0.45), 0.7)
    size = max(96, min(190, int(1650 / max(4, len(HOOK)))))
    hs = slot([x.get('band') for x in shots if x['start'] < h_end], ('mid', 'top', 'low'))
    top = {'top': 250, 'mid': 760, 'low': 1280}[hs]
    els.append(f'<div id="hkh" class="clip" data-start="0" data-duration="{h_end:.2f}" data-track-index="20" style="z-index:20"><div class="scrim" style="top:{top - 200}px"></div><div class="hook" id="hk" style="font-size:{size}px; top:{top}px">'
               + ''.join(f'<span class="w">{esc(w)}</span> ' for w in HOOK.split()) + '<div class="hstrike" id="hks"></div></div></div>')
    T('tl.fromTo("#hk .w", {y:0}, {y:-8, duration:0.8, ease:"sine.inOut", stagger:0.1}, 0);')
    T(f'tl.fromTo("#hks", {{scaleX:0}}, {{scaleX:1, duration:0.4, ease:"power3.out"}}, {b2:.2f});')
    T(f'tl.to("#hk", {{opacity:0, scale:0.92, duration:0.2, ease:"power2.in"}}, {h_end - 0.22:.2f});')
first_line_shot = 1 if HOOK else 0
for i, line in enumerate(LINES):
    n = first_line_shot + i
    if n >= len(shots): break
    a, b = shots[n]['start'], shots[n]['end']
    t = next((x for x in beats if a - 0.02 <= x < b - 0.3), a)
    lid = f'ln{i}'
    top = {'low': 1300, 'top': 250, 'mid': 820}[slot([shots[n].get('band')], ('low', 'top', 'mid'))]
    els.append(f'<div id="{lid}h" class="clip" data-start="{a:.2f}" data-duration="{b - a:.2f}" data-track-index="21" style="z-index:21"><div class="line" id="{lid}" style="top:{top}px">'
               + ''.join(f'<span class="w">{esc(w)}</span> ' for w in line.split()) + '</div></div>')
    T(f'tl.from("#{lid}", {{opacity:0, scale:0.8, duration:0.2, ease:"back.out(1.8)"}}, {t:.2f});')
    T(f'tl.from("#{lid} .w", {{opacity:0, y:34, duration:0.24, stagger:0.06, ease:"power4.out"}}, {t + 0.04:.2f});')
    if b - a > 0.6: T(f'tl.to("#{lid}", {{opacity:0, y:-20, duration:0.16, ease:"power2.in"}}, {b - 0.18:.2f});')

# ---- payoff scene: morph into the brand colour, word flips in, last photo on a 3D card ---------------
if end_scene:
    a, b = end_scene['start'], end_scene['end']
    last = next((x for x in reversed(subs) if x['kind'] != 'video'), None)
    card = f'<div class="persp2"><div class="pcard" id="pc"><img src="assets/img/{last["src"]}" class="{"cut" if last["kind"] == "cutout" else ""}" /></div></div>' if last else ''
    lead = f'<div class="lead" id="pl">' + ''.join(f'<span class="w">{esc(w)}</span> ' for w in LEAD.split()) + '</div>' if LEAD else ''
    els.append(f'<div id="pmh" class="clip" data-start="{max(0, a - 0.6):.2f}" data-duration="0.85" data-track-index="9" style="z-index:9"><div class="morph" id="pm"></div></div>')
    els.append(f'''<div id="pbh" class="clip" data-start="{a:.2f}" data-duration="{b - a:.2f}" data-track-index="10" style="z-index:10"><div class="endbg" id="pb"><div class="layer" id="pcam">
  <div class="ering" id="er1"><i></i></div><div class="ering e2" id="er2"></div>
  {lead}<div class="payoff" id="pw">{"".join(f'<span class="w">{esc(ch)}</span>' if ch != ' ' else ' ' for ch in PAYOFF)}</div><div class="uline" id="pu"></div>
  <div class="sp" id="ps1" style="left:120px;top:420px">{spark}</div><div class="sp sm2" id="ps2" style="left:900px;top:600px">{spark}</div>
  <div class="sp sm2" id="ps3" style="left:170px;top:1000px">{spark}</div><div class="sp" id="ps4" style="left:860px;top:1050px">{spark}</div>
  {card}</div></div></div>''')
    m0 = max(0, a - 0.6)
    T(f'tl.fromTo("#pm", {{scale:0, rotation:0, borderRadius:100}}, {{scale:1, duration:0.25, ease:"back.out(2)"}}, {m0:.2f});')
    T(f'tl.to("#pm", {{borderRadius:24, rotation:45, duration:0.2, ease:"power3.inOut"}}, {m0 + 0.25:.2f});')
    T(f'tl.to("#pm", {{backgroundColor:"var(--primary)", scale:14, rotation:135, duration:0.35, ease:"expo.in"}}, {m0 + 0.45:.2f});')
    eb = b - a
    T(f'tl.fromTo("#pcam", {{scale:1.12}}, {{scale:1, duration:0.9, ease:"expo.out"}}, {a:.2f}); tl.to("#pcam", {{scale:1.05, duration:{max(0.1, eb - 0.9):.2f}, ease:"none"}}, {a + 0.9:.2f});')
    T(f'tl.from("#er1", {{scale:0.4, opacity:0, duration:0.7, ease:"expo.out"}}, {a + 0.05:.2f}); tl.fromTo("#er1", {{rotation:0}}, {{rotation:240, duration:{eb:.2f}, ease:"none"}}, {a:.2f});')
    T(f'tl.from("#er2", {{scale:1.4, opacity:0, duration:0.8, ease:"expo.out"}}, {a + 0.1:.2f}); tl.fromTo("#er2", {{rotation:0}}, {{rotation:-100, duration:{eb:.2f}, ease:"none"}}, {a:.2f});')
    if LEAD: T(f'tl.from("#pl .w", {{opacity:0, y:50, duration:0.3, stagger:0.1, ease:"power4.out"}}, {a + 0.15:.2f});')
    pw_at = a + (0.45 if LEAD else 0.2)
    pb = next((t for t in beats if pw_at - 0.15 < t < pw_at + 0.35), pw_at)     # land the word on a beat when one is close
    T(f'tl.from("#pw .w", {{opacity:0, rotationX:-95, y:40, duration:0.5, stagger:0.05, ease:"back.out(1.6)"}}, {pb:.2f});')
    T(f'tl.fromTo("#pu", {{scaleX:0}}, {{scaleX:1, duration:0.45, ease:"expo.out"}}, {pb + 0.6:.2f});')
    for i in range(1, 5):
        T(f'tl.fromTo("#ps{i}", {{scale:0, rotation:-90}}, {{scale:1, rotation:0, duration:0.4, ease:"back.out(3)"}}, {pb + 0.5 + i * 0.1:.2f}); tl.to("#ps{i}", {{rotation:90, duration:{max(0.2, eb - 1.2):.2f}, ease:"none"}}, {pb + 0.9 + i * 0.1:.2f});')
    if card:      # the headline lifts to make room, then the card swings in
        T(f'tl.to("{"#pl, " if LEAD else ""}#pw, #pu, #er1, #er2", {{y:-170, duration:0.6, ease:"power3.inOut"}}, {pb + 0.65:.2f});')
        T(f'tl.fromTo("#pc", {{rotationY:75, x:260, opacity:0}}, {{rotationY:0, x:0, opacity:1, duration:0.8, ease:"expo.out"}}, {pb + 0.75:.2f});')
        T(f'tl.to("#pc", {{rotationY:-7, rotationX:4, duration:{max(0.2, eb - 1.6):.2f}, ease:"sine.inOut"}}, {pb + 1.55:.2f});')

# ---- flash and dip layers, then the CTA end card ------------------------------------------------------
els.append(f'<div id="fxh" class="clip" data-start="0" data-duration="{TOTAL:.2f}" data-track-index="60" style="z-index:60"><div class="fx" id="fx"></div><div class="dip" id="dip"></div><div class="vig"></div></div>')
if not NO_CTA:
    C = B['cta']; a = CTA_AT
    els.append(f'''<div id="ctah" class="clip" data-start="{a:.2f}" data-duration="{CTA_LEN:.2f}" data-track-index="50" style="z-index:50"><div class="canvas" id="ctabg">
  <div class="ring" id="r1"></div><div class="ring r2" id="r2"></div>
  <div class="sp" id="sp1" style="left:150px;top:380px">{spark}</div><div class="sp sm2" id="sp2" style="left:860px;top:520px">{spark}</div>
  <div class="sp sm2" id="sp3" style="left:190px;top:1150px">{spark}</div>
  <div class="persp"><div class="lcard" id="lc"><img src="assets/img/{os.path.basename(LOGO)}" /></div></div>
  <div class="ctx"><div class="eye" id="ce">{esc(C['eyebrow'])}</div><div class="ttl" id="ct">{esc(C['title'])}</div>
    <div class="det" id="cd">{esc(C['detail'])}</div><div class="url" id="cu">{esc(C['url'])} →</div>
    <div class="fc" id="cf">{esc(C.get('footnote', 'Link in the first comment'))}</div></div></div></div>''')
    T(f'tl.fromTo("#ctabg", {{opacity:0}}, {{opacity:1, duration:0.2, ease:"power2.out"}}, {a:.2f});')
    T(f'tl.from("#lc", {{rotationY:-75, rotationX:12, opacity:0, scale:0.8, duration:0.7, ease:"power3.out"}}, {a + 0.1:.2f}); tl.to("#lc", {{rotationY:8, duration:{CTA_LEN - 0.8:.2f}, ease:"sine.inOut"}}, {a + 0.8:.2f});')
    T(f'tl.from("#r1", {{scale:0.4, opacity:0, duration:0.6, ease:"power3.out"}}, {a + 0.05:.2f}); tl.to("#r1", {{rotation:90, duration:{CTA_LEN:.2f}, ease:"none"}}, {a:.2f});')
    T(f'tl.from("#r2", {{scale:0.4, opacity:0, duration:0.6, ease:"power3.out"}}, {a + 0.15:.2f}); tl.to("#r2", {{rotation:-70, duration:{CTA_LEN:.2f}, ease:"none"}}, {a:.2f});')
    for i in (1, 2, 3):
        T(f'tl.from("#sp{i}", {{scale:0, opacity:0, duration:0.4, ease:"back.out(2.5)"}}, {a + 0.3 + 0.15 * i:.2f}); tl.to("#sp{i}", {{rotation:{90 if i % 2 else -90}, duration:{CTA_LEN - 0.4:.2f}, ease:"none"}}, {a + 0.4:.2f});')
    T(f'tl.from("#ce", {{opacity:0, y:16, scaleX:1.25, duration:0.4, ease:"power3.out"}}, {a + 0.45:.2f});')
    T(f'tl.from("#ct", {{opacity:0, y:30, rotationX:-70, duration:0.5, ease:"back.out(1.6)"}}, {a + 0.65:.2f});')
    T(f'tl.from("#cd", {{opacity:0, y:16, duration:0.35, ease:"power3.out"}}, {a + 0.95:.2f});')
    T(f'tl.from("#cu", {{opacity:0, scale:0.6, duration:0.4, ease:"back.out(2)"}}, {a + 1.2:.2f}); tl.to("#cu", {{scale:1.06, duration:0.3, yoyo:true, repeat:1, ease:"sine.inOut"}}, {a + 2.1:.2f});')
    T(f'tl.from("#cf", {{opacity:0, duration:0.3}}, {a + 1.5:.2f});')

def rgb(h): h = h.lstrip('#'); return ','.join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))
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
:root {{ --primary:{P['primary']}; --accent:{P['accent']}; --bg:{P['bg']}; --ink:{P['ink']};
  --primary-rgb:{rgb(P['primary'])}; --accent-rgb:{rgb(P['accent'])}; --bg-rgb:{rgb(P['bg'])}; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; overflow:hidden; background:#000; font-family:"{HEAD}"; }}
#root {{ position:relative; width:1080px; height:1920px; overflow:hidden; background:#000; }}
.clip {{ position:absolute; left:0; top:0; width:1080px; height:1920px; pointer-events:none; }}
.layer {{ position:absolute; inset:0; }}
.cam {{ perspective:1600px; transform-origin:50% 45%; }}
.sub {{ object-fit:cover; }}
.w {{ display:inline-block; }}
.stage {{ background-color:var(--bg); background-image:radial-gradient(circle at 50% 46%, rgba(var(--accent-rgb),.22), transparent 58%); }}
.sring {{ position:absolute; left:190px; top:560px; width:700px; height:700px; border-radius:50%; border:3px solid rgba(var(--accent-rgb),.55); }}
.sring.r2 {{ left:250px; top:620px; width:580px; height:580px; border:2px dashed rgba(var(--primary-rgb),.18); }}
.cutimg {{ position:absolute; left:140px; top:510px; width:800px; height:800px; object-fit:contain; filter:drop-shadow(0 40px 50px rgba(0,0,0,.28)); }}
.scrim {{ position:absolute; left:0; right:0; top:560px; height:620px; background:radial-gradient(ellipse at 50% 50%, rgba(0,0,0,.55), rgba(0,0,0,.35) 45%, transparent 72%); }}
.hook {{ position:absolute; top:760px; left:40px; right:40px; text-align:center; font-family:"Public Sans"; font-weight:900; line-height:1; letter-spacing:-.02em;
  color:#fff; text-shadow:0 8px 40px rgba(0,0,0,.45); }}
.hstrike {{ position:absolute; left:6%; right:6%; top:52%; height:16px; border-radius:8px; background:var(--accent); transform-origin:0 50%; box-shadow:0 4px 18px rgba(0,0,0,.3); }}
.line {{ position:absolute; top:1300px; left:0; right:0; margin:0 auto; width:max-content; max-width:960px; text-align:center; font-family:"Montserrat"; font-weight:800;
  font-size:56px; letter-spacing:.06em; text-transform:uppercase; color:var(--bg); background:rgba(var(--primary-rgb),.9); border-radius:22px; padding:14px 34px 18px; }}
.morph {{ position:absolute; left:440px; top:860px; width:200px; height:200px; border-radius:100px; background:var(--accent); }}
.endbg {{ position:absolute; inset:0; background:var(--primary); perspective:1400px; overflow:hidden; }}
.ering {{ position:absolute; left:190px; top:420px; width:700px; height:700px; border-radius:50%; border:3px solid rgba(var(--accent-rgb),.55); }}
.ering i {{ position:absolute; left:337px; top:-11px; width:22px; height:22px; border-radius:11px; background:var(--accent); }}
.ering.e2 {{ left:250px; top:480px; width:580px; height:580px; border:2px dashed rgba(var(--bg-rgb),.25); }}
.lead {{ position:absolute; top:560px; width:1080px; text-align:center; font-family:"Montserrat"; font-weight:700; font-size:72px; letter-spacing:.04em; color:var(--bg); }}
.payoff {{ position:absolute; top:650px; width:1080px; text-align:center; font-family:"{SERIF}"; font-style:{ACC_STYLE}; font-weight:600; font-size:200px; line-height:1.05; color:var(--accent); transform-style:preserve-3d; }}
.payoff .w {{ transform-origin:50% 100%; }}
.uline {{ position:absolute; left:240px; width:600px; top:890px; height:6px; border-radius:3px; background:var(--bg); transform-origin:50% 50%; }}
.persp2 {{ position:absolute; left:0; right:0; top:900px; perspective:1400px; }}
.pcard {{ margin:0 auto; width:560px; height:560px; border-radius:40px; overflow:hidden; background:var(--bg); box-shadow:0 0 0 6px var(--accent), 0 30px 70px rgba(0,0,0,.35); }}
.pcard img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.pcard img.cut {{ object-fit:contain; padding:40px; }}
.fx {{ position:absolute; inset:0; background:#fff; opacity:0; }}
.dip {{ position:absolute; inset:0; background:#000; opacity:0; }}
.vig {{ position:absolute; inset:0; background:radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,.28)); }}
.canvas {{ position:absolute; inset:0; background-color:var(--bg);
  background-image:linear-gradient(rgba(var(--primary-rgb),.07) 2px, transparent 2px), linear-gradient(90deg, rgba(var(--primary-rgb),.07) 2px, transparent 2px); background-size:60px 60px; }}
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
{B.get('extra_css', '')}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL:.2f}" data-width="1080" data-height="1920" data-motion-blur="on">
{chr(10).join(els)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.set("#fx, #dip", {{opacity:0}}, 0);
{chr(10).join(tw)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
'''

# clips: cut each video subject to 1080x1920 once, silent (the music comes in finish.sh)
for i, sub in enumerate(subs):
    if sub['kind'] != 'video': continue
    name = f'sub{i}.mp4'
    dst = f'{A}/{name}'
    run(['ffmpeg', '-v', 'error', '-y', '-i', sub['src'], '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30',
         '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-g', '15', '-pix_fmt', 'yuv420p', dst])
    page = page.replace(f'src="{esc(sub["src"])}"', f'src="assets/img/{name}"')
open(f'{HF}/index.html', 'w').write(page)
print(f'{len(shots)} shots{" + payoff scene" if end_scene else ""}{" + end card" if not NO_CTA else ""}, '
      f'{len(subs)} subjects, {plan.get("bpm") or "?"} BPM, total {TOTAL} s -> {HF}')
