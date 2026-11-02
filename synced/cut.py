"""cut.py VIDEO CUTLIST.json OUT.mp4 : cut your keeper lines into one tight, vertical 1080x1920 clip.

CUTLIST.json is a list of the lines to keep, in the order you want them (times from lines.py):
  [{"in": 59.78, "out": 62.28}, {"in": 24.78, "out": 26.84, "gap": 0.15}, ...]
  in/out  seconds in the raw video. Pad a little: start ~0.04 s early, end ~0.08 s late, so no word is clipped.
  gap     breathing room after the line (default 0.15 s). Use more after a punchline, less mid-sentence.
Every other line gets a gentle 1.12x punch-in so the jump cuts feel intentional. Sound and picture of each
line are cut together in one pass, so lips stay in sync. iPhone HDR footage is converted with Apple's avconvert.
Re-run transcribe.sh on OUT.mp4 afterwards: those word times drive the graphics."""
import json, os, shutil, subprocess, sys, tempfile

if len(sys.argv) < 4: sys.exit(__doc__)
SRC, LIST, OUT = (os.path.abspath(x) for x in sys.argv[1:4])
spec = json.load(open(LIST))
FPS = 30
tmp = tempfile.mkdtemp(prefix='cut-')

# iPhone HDR (HLG/PQ): convert with Apple's own avconvert first, exactly what Photos does (no extra grading on top)
pr = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=color_transfer',
                     '-of', 'default=nw=1:nk=1', SRC], capture_output=True, text=True).stdout.strip().strip(',')
hdr = pr in ('arib-std-b67', 'smpte2084')
if hdr and shutil.which('avconvert'):
    sdr = f'{tmp}/sdr.mp4'
    print('iPhone HDR footage: converting colors with Apple avconvert (one time, about a minute)...', flush=True)
    subprocess.run(['avconvert', '-s', SRC, '-p', 'Preset1920x1080', '-o', sdr], check=True, capture_output=True)
    SRC = sdr
# vertical 1080x1920: fill the frame (center crop if the source isn't 9:16)
base = 'scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920'
punch = 'scale=1210:2150:flags=lanczos,crop=1080:1920,unsharp=5:5:0.5'

parts = []
for i, s in enumerate(spec):
    a, b = float(s['in']), float(s['out']); gap = float(s.get('gap', 0.15))
    speech = b - a; dur = round((speech + gap) * FPS) / FPS
    vf = f"fps={FPS},{base}" + (f",{punch}" if i % 2 else '') + ',format=yuv420p'
    af = (f"atrim=0:{speech:.3f},afade=t=in:d=0.03,afade=t=out:st={max(0, speech - 0.05):.3f}:d=0.05,"
          f"apad,atrim=0:{dur:.3f},aresample=48000")
    out = f'{tmp}/p{i:03d}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{a:.3f}', '-i', SRC, '-t', f'{dur:.3f}', '-vf', vf, '-af', af,
                    '-frames:v', str(round(dur * FPS)), '-c:v', 'libx264', '-crf', '16', '-preset', 'medium',
                    '-c:a', 'aac', '-b:a', '256k', '-ac', '2', out], check=True)
    parts.append(out)
    print(f'line {i + 1}: {a:.2f}-{b:.2f} -> {dur:.2f} s', flush=True)

open(f'{tmp}/list.txt', 'w').write(''.join(f"file '{p}'\n" for p in parts))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{tmp}/list.txt', '-c', 'copy',
                '-movflags', '+faststart', OUT], check=True)
r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', OUT], capture_output=True, text=True)
print(f'cut -> {OUT} ({float(r.stdout):.1f} s){" (HDR converted)" if hdr else ""}')
