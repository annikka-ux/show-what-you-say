"""lines.py VIDEO [--from S] [--to S] : every spoken line of a raw recording, numbered, with exact start/end.

Finds where you are actually talking (loudness, not guesses), then transcribes each stretch on its own, so the
times are exact even when you pause a lot or redo a line. Use it to pick the keepers for cut.py:
  12  45.38-52.74  On the right, it shows exactly, anything on the screen shows exactly what I'm trying to say.
Retakes show up as near-duplicate lines; keep the cleanest (usually the last one).
Writes VIDEO-lines.json next to the video. Needs whisper-cli + the model from setup.sh (WHISPER_MODEL to override)."""
import array, json, math, os, subprocess, sys, tempfile, wave

args = sys.argv[1:]
if not args: sys.exit(__doc__)
VIDEO = os.path.abspath(args[0])
def opt(name, default):
    return float(args[args.index(name) + 1]) if name in args else default
T0, T1 = opt('--from', 0.0), opt('--to', 1e9)
MODEL = os.environ.get('WHISPER_MODEL', os.path.expanduser('~/whisper-models/ggml-medium.bin'))
if not os.path.isfile(MODEL): sys.exit(f'No speech model at {MODEL}. Run setup.sh first.')
LANG = os.environ.get('WHISPER_LANG', 'en')
tmp = tempfile.mkdtemp(prefix='lines-')

wav = f'{tmp}/all.wav'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', VIDEO, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
w = wave.open(wav); sr = w.getframerate(); pcm = array.array('h', w.readframes(w.getnframes()))
hop = int(sr * 0.02)

# speech islands: 20 ms windows louder than -55 dB, joined across gaps shorter than 0.3 s
isl, start, last = [], None, None
for i in range(0, len(pcm) - hop, hop):
    s = pcm[i:i + hop]; t = i / sr
    loud = 20 * math.log10(math.sqrt(sum(x * x for x in s) / hop) / 32768 + 1e-9) > -55
    if loud:
        if start is None: start = t
        last = t + 0.02
    elif start is not None and t - last > 0.30:
        isl.append((start, last)); start = None
if start is not None: isl.append((start, last))
isl = [(a, b) for a, b in isl if b - a > 0.12 and b > T0 and a < T1]


def words(a, b):
    part = f'{tmp}/p.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, a - 0.1):.2f}', '-to', f'{b + 0.15:.2f}', '-i', wav, part], check=True)
    subprocess.run(['whisper-cli', '-m', MODEL, '-l', LANG, '-f', part, '-of', f'{tmp}/p', '-oj'], check=True, capture_output=True)
    d = json.load(open(f'{tmp}/p.json'))
    txt = ' '.join(x['text'].strip() for x in d['transcription']).strip()
    return '' if txt.startswith('[') else txt


out = []
for n, (a, b) in enumerate(isl, 1):
    txt = words(a, b)
    if not txt: continue
    out.append({'n': n, 'in': round(a, 2), 'out': round(b, 2), 'text': txt})
    print(f'{n:3d}  {a:7.2f}-{b:7.2f}  {txt}', flush=True)
json.dump(out, open(os.path.splitext(VIDEO)[0] + '-lines.json', 'w'), indent=1)
