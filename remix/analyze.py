"""Read a reference edit and write down how it is built, so remix.py can rebuild it with your own photos.
Finds every cut, the tempo and beats of its music, the camera move inside each shot (push in, pull out,
pan, tilt, handheld, still) and how each shot arrives (hard cut, white flash, dip to black, whip).
Only the timing and structure are kept: no frame, sound or person from the reference ends up in your video.

usage: python3 analyze.py REFERENCE.mp4 [PLAN.json] [--threshold 0.30]
  REFERENCE.mp4  any edit you want to copy the rhythm of (a reel you saved, your own past video)
  PLAN.json      default <reference>.plan.json next to it
  --threshold    cut sensitivity, 0.2 (finds more cuts) to 0.5 (only hard changes); default 0.30

Uses only ffmpeg and Python's standard library. If numpy is installed, camera moves are measured
frame by frame; without it each shot is still timed exactly but its move is guessed from its energy."""
import json, math, os, re, subprocess, sys
from array import array

args = [a for a in sys.argv[1:]]
TH = 0.30
if '--threshold' in args:
    i = args.index('--threshold'); TH = float(args[i + 1]); del args[i:i + 2]
if not args: raise SystemExit(__doc__)
REF = os.path.abspath(args[0])
OUT = os.path.abspath(args[1]) if len(args) > 1 else os.path.splitext(REF)[0] + '.plan.json'
SW, SH, SFPS = 72, 128, 15      # tiny grayscale frames for measuring motion and brightness

def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, check=True, **kw)

def probe():
    r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', REF], text=True)
    j = json.loads(r.stdout)
    return float(j['format']['duration']), any(s.get('codec_type') == 'audio' for s in j.get('streams', []))

DUR, HAS_AUDIO = probe()

# ---- cuts: ffmpeg's scene score jumps when the picture changes all at once ----------------------
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', REF, '-an', '-vf', f"scale=270:-2,select='gt(scene,{TH})',showinfo", '-f', 'null', '-'],
                   capture_output=True, text=True)
cuts = sorted({round(float(m), 3) for m in re.findall(r'pts_time:([0-9.]+)', r.stderr)})
cuts = [c for c in cuts if 0.25 < c < DUR - 0.25]
merged = []
for c in cuts:                  # a flash or a fast whip can trigger twice in a row; keep the first
    if not merged or c - merged[-1] > 0.2: merged.append(c)
cuts = merged

# ---- tiny frames: brightness for flashes and dips, motion for camera moves ------------------------
raw = run(['ffmpeg', '-v', 'error', '-i', REF, '-an', '-vf', f'fps={SFPS},scale={SW}:{SH},format=gray', '-f', 'rawvideo', '-']).stdout
FS = SW * SH
frames = [raw[i:i + FS] for i in range(0, len(raw) - FS + 1, FS)]
luma = [sum(f) / FS for f in frames]
def fidx(t): return max(0, min(len(frames) - 1, int(round(t * SFPS))))

try:
    import numpy as np
except ImportError:
    np = None

def measure_move(a, b):
    """Overall pan (fraction of frame) and zoom across frames a..b, plus a jitter score for handheld."""
    if np is None or b - a < 3: return None
    F = [np.frombuffer(frames[k], np.uint8).reshape(SH, SW).astype(np.float32) for k in range(a, b)]
    yy, xx = np.mgrid[0:SH, 0:SW]
    cx, cy = (SW - 1) / 2, (SH - 1) / 2
    zooms = tuple(round(0.94 + 0.01 * i, 2) for i in range(13))   # 0.94 .. 1.06
    tot_dx = tot_dy = tot_z = 0.0; steps = []
    G = 3                        # compare frames 0.2 s apart: small zooms add up enough to measure
    for k in range(0, len(F) - G, G):
        p, q = F[k], F[k + G]
        # coarse shift by phase correlation (handles fast pans), then zoom + 1 px refinement by brute force
        R = np.fft.fft2(q - q.mean()) * np.conj(np.fft.fft2(p - p.mean()))
        r = np.fft.ifft2(R / (np.abs(R) + 1e-6)).real
        py, px = np.unravel_index(int(np.argmax(r)), r.shape)
        px = px - SW if px > SW // 2 else px; py = py - SH if py > SH // 2 else py
        m = max(6, abs(px) + 3, abs(py) + 3)
        if 2 * m >= min(SW, SH) - 8: continue
        best = (1e18, 0, 0, 1.0)
        for z in zooms:          # q = p seen through a camera that zoomed by z, content shifted by dx, dy
            sx = np.clip(((xx - cx) / z + cx).round().astype(int), 0, SW - 1)
            sy = np.clip(((yy - cy) / z + cy).round().astype(int), 0, SH - 1)
            pz = p[sy, sx]
            for dx in (px - 1, px, px + 1):
                for dy in (py - 1, py, py + 1):
                    sh = np.roll(np.roll(pz, dy, 0), dx, 1)[m:-m, m:-m]
                    e = float(np.abs(sh - q[m:-m, m:-m]).mean())
                    if e < best[0]: best = (e, dx, dy, z)
        _, dx, dy, z = best
        tot_dx += dx / SW; tot_dy += dy / SH; tot_z += math.log(z); steps.append((dx, dy))
    # handheld = the shift keeps changing direction
    turns = sum(1 for i in range(1, len(steps)) if steps[i][0] * steps[i - 1][0] < 0 or steps[i][1] * steps[i - 1][1] < 0)
    flips = turns / max(1, len(steps) - 1)
    return tot_dx, tot_dy, tot_z, flips

def energy(a, b):
    if b - a < 2: return 0.0
    d = 0
    for k in range(a, b - 1):
        f, g = frames[k], frames[k + 1]
        d += sum(abs(f[i] - g[i]) for i in range(0, FS, 7))
    return d / ((b - a - 1) * (FS / 7) * 255)

# ---- beats: onset strength from the music, tempo by autocorrelation ------------------------------
bpm, beats = None, []
if HAS_AUDIO:
    SR, HOP = 11025, 256
    pcm = array('h', run(['ffmpeg', '-v', 'error', '-i', REF, '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-']).stdout)
    env = []
    for i in range(0, len(pcm) - HOP, HOP):
        s = 0
        for v in pcm[i:i + HOP:2]: s += v * v
        env.append(math.log(1 + s / (HOP / 2)))
    on = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    fps = SR / HOP
    if on and max(on) > 0:
        ac = {lag: sum(on[i] * on[i - lag] for i in range(lag, len(on)))
              for lag in range(int(fps * 60 / 180) - 1, int(fps * 60 / 70) + 2)}       # 70-180 BPM
        lag = max(list(ac)[1:-1], key=ac.get)
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        den = y0 - 2 * y1 + y2
        flag = lag + (0.5 * (y0 - y2) / den if den else 0)      # between two hops: interpolate the peak
        def fit(per, ph):       # how much onset lands exactly on a beat grid
            return sum(on[k] for k in (int(round(ph + j * per)) for j in range(int((len(on) - 1 - ph) / per) + 1)))
        score, flag, phase = max((fit(per, ph), per, ph) for per in (flag * (0.97 + 0.002 * i) for i in range(31))
                                 for ph in range(int(per) + 1))
        bpm = round(60 * fps / flag, 1)
        beats = [round((phase + j * flag + 1) / fps, 3) for j in range(int((len(on) - 1 - phase) / flag) + 1)]
if not bpm and cuts:               # silent reference: the cuts are the rhythm
    gaps = sorted(b - a for a, b in zip([0] + cuts, cuts + [DUR]))
    g = gaps[len(gaps) // 2]
    while g < 0.33: g *= 2
    while g > 0.86: g /= 2
    bpm = round(60 / g, 1); beats = [round(i * g, 3) for i in range(int(DUR / g) + 1)]

# ---- shots ----------------------------------------------------------------------------------------
edges = [0.0] + cuts + [round(DUR, 3)]
shots = []
for n, (a, b) in enumerate(zip(edges, edges[1:])):
    fa, fb = fidx(a), fidx(b)
    e = energy(fa, fb)
    m = measure_move(fa + 1, fb - 1)
    move, strength = 'still', 0.3
    if m:
        dx, dy, z, flips = m
        zs, ps = abs(z) / 0.035, max(abs(dx), abs(dy)) / 0.05       # whichever move is clearer wins
        if flips > 0.45 and e > 0.04: move, strength = 'handheld', min(1, e * 8)
        elif zs >= ps and zs > 1: move, strength = ('push_in' if z > 0 else 'pull_out'), min(1, abs(z) / 0.15)
        elif ps > 1 and abs(dx) >= abs(dy): move, strength = ('pan_left' if dx > 0 else 'pan_right'), min(1, abs(dx) / 0.3)
        elif ps > 1: move, strength = ('tilt_up' if dy > 0 else 'tilt_down'), min(1, abs(dy) / 0.3)
    else:
        move = 'push_in' if e > 0.05 else 'still'; strength = min(1, 0.3 + e * 6)
    arrive = 'cut'
    if n:
        k = fidx(a)
        around = luma[max(0, k - 4):k] + luma[k + 3:k + 7]
        peak = max(luma[max(0, k - 1):k + 3])
        low = min(luma[max(0, k - 3):k + 3])
        if low < 18 and min(luma[k + 2:k + 6] or [0]) > 30: arrive = 'dip'
        elif around and peak - sum(around) / len(around) > 45: arrive = 'flash'
        elif energy(max(0, k - 3), k) > 0.12: arrive = 'whip'
    shots.append({'start': round(a, 3), 'end': round(b, 3), 'move': move, 'strength': round(strength, 2),
                  'energy': round(e, 3), 'arrive': arrive})

plan = {'source': os.path.basename(REF), 'duration': round(DUR, 3), 'bpm': bpm, 'beats': beats, 'shots': shots,
        'measured_moves': np is not None}
json.dump(plan, open(OUT, 'w'), indent=1)
avg = DUR / len(shots)
print(f'{len(shots)} shots, avg {avg:.2f} s, {bpm or "no"} BPM, arrivals ' +
      ', '.join(f'{k} {sum(s["arrive"] == k for s in shots)}' for k in ('cut', 'flash', 'dip', 'whip')) + f' -> {OUT}')
if np is None: print('(numpy not installed: camera moves were guessed, not measured. pip3 install numpy to measure them.)')
