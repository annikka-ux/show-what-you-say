"""Make the reels yours: saves your brand (colors, logo, end-card CTA) into my-brands.json (private to your Mac).

usage:
  python3 brand.py --status
      prints READY and your brand key, or NEEDS-BRAND if only the example brands exist.
  python3 brand.py --key mine --name "Your Name" --logo ~/Downloads/logo.png --primary "#1f4e79" --accent "#f2b705"
                   --eyebrow "WANT HELP WITH THIS?" --title "Book a free call" --detail "For busy coaches"
                   --url "yoursite.com/call" [--bg "#faf7f0"] [--ink "#1f2937"] [--fix "Anika=Annika"]
      --primary  your main brand color (cards, captions), dark enough for white text
      --accent   your highlight color (payoff words, sparkles)
      --logo     PNG or JPG (a square-ish logo works best); copied to img/<key>-logo.png
      --fix      words the transcript gets wrong, e.g. your name: "Anika=Annika" (repeatable)
The first brand you save becomes the default. Claude asks these on your first /reel."""
import argparse, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = f'{HERE}/my-brands.json'      # your brands (git-ignored); the examples stay in brands.json
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
def lum(h):
    c = [x / 255 for x in rgb(h)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


p = argparse.ArgumentParser()
p.add_argument('--status', action='store_true')
p.add_argument('--key', default='mine')
for f in ('name', 'logo', 'primary', 'accent', 'eyebrow', 'title', 'detail', 'url', 'bg', 'ink'):
    p.add_argument(f'--{f}')
p.add_argument('--fix', action='append', default=[])
a = p.parse_args()
brands = json.load(open(PATH)) if os.path.exists(PATH) else {}

if a.status:
    mine = [k for k in brands if k != '_default']
    print(f"READY {brands.get('_default', mine[0])}" if mine else 'NEEDS-BRAND')
    sys.exit(0)

missing = [f for f in ('name', 'logo', 'primary', 'accent', 'title', 'url') if not getattr(a, f)]
if missing: sys.exit('brand.py: please give ' + ', '.join('--' + m for m in missing))
for f in ('primary', 'accent', 'bg', 'ink'):
    v = getattr(a, f)
    if v and not HEX.match(v): sys.exit(f'brand.py: --{f} must look like #1f4e79, got {v!r}')
logo = os.path.expanduser(a.logo)
if not os.path.isfile(logo): sys.exit(f'brand.py: logo not found: {logo}')
import filecmp
if os.path.exists(f'{HERE}/img/logo.png') and filecmp.cmp(logo, f'{HERE}/img/logo.png', shallow=False):
    sys.exit('brand.py: that is the kit\'s "YOUR LOGO" placeholder. Use your own logo, or make one with your initials.')

os.makedirs(f'{HERE}/img', exist_ok=True)
dest = f'{HERE}/img/{a.key}-logo.png'
if logo.lower().endswith('.png'):
    shutil.copy(logo, dest)
else:   # JPG, HEIC, etc. -> PNG with the Mac's built-in sips
    subprocess.run(['sips', '-s', 'format', 'png', logo, '--out', dest], check=True, capture_output=True)

bg = a.bg or '#faf7f0'
ink = a.ink or '#1f2937'
warn = []
if contrast(a.primary, '#ffffff') < 3: warn.append(f'primary {a.primary} is light: white caption text on it may be hard to read; pick a darker shade')
if contrast(a.accent, bg) < 1.6: warn.append(f'accent {a.accent} is close to the background {bg}; payoff words may fade')

brands[a.key] = {
    'palette': {'primary': a.primary, 'accent': a.accent, 'bg': bg, 'ink': ink, 'red': '#b5544a'},
    'fonts': {'head': 'Montserrat', 'accent': 'Cormorant'},
    'logo': f'img/{a.key}-logo.png',
    'cta': {'eyebrow': (a.eyebrow or 'READY FOR THE NEXT STEP?').upper(), 'title': a.title,
            'detail': a.detail or a.name, 'url': a.url, 'footnote': 'Link in the first comment'},
    'fix_words': dict(x.split('=', 1) for x in a.fix if '=' in x),
}
brands.setdefault('_default', a.key)
json.dump(brands, open(PATH, 'w'), indent=2, ensure_ascii=False)
print(f'saved brand {a.key!r} (logo {dest})')
for w in warn: print('note:', w)
