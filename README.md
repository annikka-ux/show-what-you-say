# Show What You Say: word-synced reels with Claude Code

*Built by Annikka at [TAP OBM](https://tapobm.com). Free to use under the MIT license.*

Turn a talking-head video into a vertical reel where **every graphic shows exactly what you're saying that second**: karaoke captions, the Signature look (cream, teal, gold, kinetic type, shape morphs, rings, sparkles, a 3D logo card) and a CTA end card. Or **remix any edit you like**: give it a reel whose rhythm you love plus a few of your own photos, and it rebuilds that edit around them, cut for cut and beat for beat. It runs locally on your Mac with free tools; you need Claude Code, which comes with a paid Claude plan (Pro or higher).

- **Under the hood** it uses a free, open-source HTML-to-video renderer (credited in `THIRD_PARTY_NOTICES.md`). Its Claude Code skills are included in `skills/`, and the renderer downloads automatically the first time you render.

## What's inside

| Folder | What it is |
|---|---|
| `signature-look/` | The 10-second Signature look sample (`index.html`) and its render (`signature-look-preview.mp4`). Use it as a reference for title cards and b-roll. |
| `synced/` | The word-synced pipeline: `transcribe.sh` → `gen.py` + a beats file → `finish.sh`. Includes a demo you can run in 2 minutes. |
| `synced/brands.json` | Your colors, fonts, logo and end-card CTA. Two example skins: `classic` (cream/teal/gold) and `bright` (teal/yellow). |
| `remix/` | Remix an edit: `analyze.py` reads a reference video's cuts, beats, camera moves and transitions; `remix.py` rebuilds it with your photos or clips in the Signature look; `finish.sh` adds music. Four presets if you have no reference. Includes a demo. |
| `skills/reel/` | The `/reel` Claude Code skill: the whole standard, from script to cut, graphics, QA and hand-off. |
| `skills/remix/` | The `/remix` Claude Code skill: reference (or preset) + your photos → finished reel. |
| `skills/hyperframes*`, `skills/media-use/` | The renderer's own Claude Code skills (Apache-2.0, unchanged). |

## Setup (once)

```bash
git clone https://github.com/annikka-ux/show-what-you-say.git ~/show-what-you-say
```

```bash
~/show-what-you-say/setup.sh
```

This installs Node, ffmpeg and whisper.cpp with Homebrew if they're missing, downloads the free whisper medium model (1.5 GB), and copies the skills into `~/.claude/skills`. Restart Claude Code afterwards.

Optional: turn off the renderer's anonymous usage stats with `npx hyperframes telemetry --help`. Don't sign in to HeyGen or set a `HEYGEN_API_KEY` unless you want its paid features. Nothing in this kit needs them.

## Try the demo

```bash
cd ~/show-what-you-say/synced && ./make_demo.sh && ./transcribe.sh demo.mp4 && python3 gen.py demo.mp4 demo-words.json beats_example classic && ./finish.sh hf-classic demo.mp4 demo-classic.mp4
```

`demo-classic.mp4` is a 20-second reel built on a test voice. Swap `classic` for `bright` to see the second skin.

## Make a real reel

The easy way: open Claude Code and type `/reel ~/Downloads/my-video.mov`. It writes the script and cut list first, waits for your OK, then builds, checks and hands back the MP4.

By hand:

1. **Cut it tight.** Keep only your best 45-60 seconds, no retakes. The video should be 1080x1920 (vertical).
2. **Transcribe:** `./transcribe.sh cut.mp4` writes `cut-words.json` with a start time for every word.
3. **Write the beats:** copy `beats_example.py` to `beats_myvideo.py`. Each beat enters on the word it illustrates (`g.at('order')` looks up the time) and leaves when you move on. Ready-made beats: `card`, `old_vs_new`, `tag`, `side_chips`, `checklist`, `point`, `cutaway_message`, `big_number`, `chat`.
4. **Generate:** `python3 gen.py cut.mp4 cut-words.json beats_myvideo classic`
5. **Check:** `cd hf-classic && npx --yes hyperframes@0.8.210 check && npx --yes hyperframes@0.8.210 snapshot --at 2,5,9`
6. **Finish:** `./finish.sh hf-classic cut.mp4 final.mp4 music.mp3` renders the video and adds your voice at -14 LUFS, a 6% music bed and a fade in/out, plus `final-cover.jpg`.

Music isn't included (license). Free beds: https://mixkit.co/free-stock-music/ (pick confident, driving tracks).

## Remix an edit you like

Saw a reel whose pacing you love? Save it to your Mac, pick 3-8 of your own photos (or a product shot with a transparent background, or short clips), and type in Claude Code:

`/remix ~/Downloads/their-reel.mp4 ~/Pictures/me1.jpg ~/Pictures/me2.jpg ~/Pictures/product.png hook: Busy. payoff: Booked.`

What it does:

1. **Reads the reference** (`remix/analyze.py`): every cut, the tempo and beats of the music, the camera move inside each shot (push in, pull out, pan, tilt, handheld) and how each shot arrives (hard cut, white flash, dip to black, whip). It keeps only that timing and structure, never the other video's frames or people.
2. **Rebuilds it with your subjects** (`remix/remix.py`): your photos take turns across the shots with the same moves, punch on the beat, and arrive with the same transitions. A PNG with a transparent background floats on your brand colours with rings and sparkles. Optional words in the Signature look: a hook word struck out on the second beat, one short line per shot, and a payoff scene where a gold shape morphs into your brand colour and the word flips in letter by letter, with your last photo on a 3D card.
3. **Finishes it** (`remix/finish.sh`): renders, adds your music at social loudness, fades, writes a cover frame, and ends on your CTA card.

No reference? Use a preset instead: `hype`, `cinematic`, `reveal` or `story`.

Try the demo (it makes its own test reference and test photos, nothing downloaded):

```bash
cd ~/show-what-you-say/remix && ./make_demo.sh && python3 analyze.py demo-ref.mp4 && python3 remix.py demo-ref.plan.json classic demo-photos/*.jpg demo-photos/product.png --hook "Busy." --lead "Now you're" --payoff "Booked." --lines "Answer first|Pause|End down" && ./finish.sh hf-remix-classic demo-remix.mp4 demo-ref.mp4
```

Good to know: it moves your real photos and clips to someone else's rhythm; it does not generate AI footage of you. Only use the reference's own sound if you have the rights to it (your own video, a licensed track). Camera moves are measured when Python has numpy (`pip3 install numpy`); without it the cuts, beats and transitions are still exact and the moves are guessed.

## Make it your brand

Edit `synced/brands.json`: `primary`, `accent`, `bg`, `ink`, and swap your logo into `synced/img/`. For the Signature look sample, change the five colors at the top of `signature-look/index.html` and replace `assets/img/logo.png`.

## The rules that make it look good

- A graphic shows **exactly** what you're saying that second. Nothing decorative.
- Something changes every 2-3 seconds.
- Hook line on screen at frame 0, then repeated near the end.
- Never cover the face. Cards go in the lower-middle area, chips at the sides, captions just below.
- Every version ends with a CTA card. The clickable link goes in the first comment, not the caption.

## Credits

Built by Annikka at [TAP OBM](https://tapobm.com), where we build AI employees that run operations inside service businesses. If this kit saves you an afternoon, that's the idea. Questions or wins: share them in the Discussions tab.

License: MIT (see `LICENSE`). The renderer (HyperFrames), the fonts and whisper.cpp keep their own licenses (see `THIRD_PARTY_NOTICES.md`).
