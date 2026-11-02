"""lookaway.py CUT.mp4 : two checks on your cut, so the reel only shows you looking at the camera and no card
ever sits on your face.

1. Look-aways: moments your eyes leave the camera (reading notes, glancing off). Each one gets covered by a
   full-screen cutaway in the beats file (or cut out), so viewers only see you talking to them.
2. Layout: where your face sits in the frame. Prints LAYOUT=low (face high in frame: cards go below it, the
   default) or LAYOUT=high (face low in frame: cards go above your head, captions under your chin).
   Pass it to gen.py:  LAYOUT=high python3 gen.py ...

Uses Apple's on-device face landmarks (free). Calibrates to YOUR normal on-camera gaze first, so it works
whatever the camera angle. Needs Swift (comes with Apple's free developer tools)."""
import os, shutil, statistics, subprocess, sys, tempfile

if len(sys.argv) < 2: sys.exit(__doc__)
VID = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 8
tmp = tempfile.mkdtemp(prefix='eyes-')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', VID, '-vf', f'fps={FPS},scale=720:-2', '-q:v', '3', f'{tmp}/f%05d.jpg'], check=True)
binp = os.path.expanduser('~/.cache/show-what-you-say/eyes')
if not os.path.exists(binp) or os.path.getmtime(binp) < os.path.getmtime(f'{HERE}/eyes.swift'):
    os.makedirs(os.path.dirname(binp), exist_ok=True)
    subprocess.run(['swiftc', '-O', f'{HERE}/eyes.swift', '-o', binp], check=True, capture_output=True)
lines = subprocess.run([binp, tmp], capture_output=True, text=True).stdout.splitlines()
shutil.rmtree(tmp, ignore_errors=True)

rows = []
for l in lines:
    p = l.split()
    t = (int(p[0][1:6]) - 1) / FPS
    if p[1] == 'noface': rows.append((t, None, None, None)); continue
    fy, fh = float(p[3]), float(p[5])
    px, py = (float(p[7]) + float(p[8])) / 2, (float(p[9]) + float(p[10])) / 2
    rows.append((t, px, py, (fy, fh)))
seen = [r for r in rows if r[1] == r[1] and r[1] is not None]
if not seen: sys.exit('No face found in the cut.')

# calibrate: the median horizontal pupil position is "looking at the camera" for this person + this camera
base = statistics.median(r[1] for r in seen)
spread = statistics.median(abs(r[1] - base) for r in seen) or 0.03
lim = max(0.14, 4 * spread)
away = [r[0] for r in seen if abs(r[1] - base) > lim and r[2] > -0.15]    # skip blinks (low y)

spans = []
for t in away:
    if spans and t - spans[-1][1] <= 0.4: spans[-1][1] = t
    else: spans.append([t, t])
spans = [(a, b + 1 / FPS) for a, b in spans]
print(f'Look-aways ({len(spans)}):' if spans else 'Look-aways: none, you stay on camera the whole time.')
for a, b in spans:
    print(f'  {a:6.2f}-{b:6.2f} s  -> cover with a full-screen cutaway (or recut)')

top = statistics.median(r[3][0] for r in seen); bot = statistics.median(r[3][0] + r[3][1] for r in seen)
layout = 'high' if top > 0.30 else 'low'
print(f'Face sits at {top * 1920:.0f}-{bot * 1920:.0f} px of 1920.  LAYOUT={layout}'
      + ('  (face is low: cards above the head, captions under the chin)' if layout == 'high' else '  (cards below the face)'))
