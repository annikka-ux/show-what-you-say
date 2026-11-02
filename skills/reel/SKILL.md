---
name: reel
description: Show What You Say reel, start to finish. Use when the user types /reel, or asks to make, cut or edit a reel or short from a video, class, call or file. Turns talking-head footage into a vertical reel where every graphic shows exactly what is being said, with karaoke captions, a music bed and a CTA end card. Brand check, script and cut list first, then build, QA and hand over.
argument-hint: "[video file] [brand key, default: yours] [what the CTA pushes]"
---
<!-- kit: show-what-you-say -->

# /reel: the Show What You Say standard

Input: `$ARGUMENTS`. Expected: the video, optionally the brand and the goal of the end card. Ask only if the video is missing. The kit lives where it was installed (default `~/show-what-you-say`; all commands below run from its `synced/` folder). Load the `hyperframes` skill before building.

Who you're working with: often someone who has never edited a video or used a terminal. Talk in plain words, never paste code at them, do the technical work yourself, and tell them what's happening in one short line at each step ("Finding your best lines now..."). Keep your own work lean (read the outputs you need, not whole files) so the edit fits in their plan's usage. If the usage limit stops you mid-edit, everything is saved in the reel's folder: on the next run, read `SCRIPT.md` and the `STATUS` line in it and continue from there.

## 0. First run: their brand (once)
- Run `python3 brand.py --status`. If it prints `NEEDS-BRAND`, ask these in ONE message, with examples:
  1. Your name or business name (how it should appear).
  2. Your logo: drag the file in here (PNG or JPG). No logo yet? I'll make a simple one with your initials.
  3. Your two brand colors (a main one and a highlight), as color codes if you have them, or just describe them ("navy and gold") and I'll pick matching codes.
  4. What should people do at the end, and the link? (e.g. "Book a free call, calendly.com/you")
- No logo: make a 600x600 PNG circle in their main color with their initials (any simple method, e.g. a small HTML page rendered with `npx hyperframes`, or Python if available) and use it.
- Save it: `python3 brand.py --key mine --name ... --logo ... --primary ... --accent ... --eyebrow ... --title ... --detail ... --url ...` (also `--fix "Wrong=Right"` for their name if the transcript misspells it). Read any `note:` it prints and adjust the color if it warns. Show them one line: "Saved your brand. Every reel will end on your logo and link."
- Never build a reel that ends on "YOUR LOGO" or "yoursite.com".

## 1. Find the footage and the best lines
- Work in a folder next to the video: `<video name>-reel/`. Start `SCRIPT.md` there with a `STATUS:` line you update after each step.
- `python3 lines.py VIDEO` lists every spoken line with exact start/end (it handles long pauses and retakes). Retakes show up as near-duplicates; keep the cleanest, usually the last one.
- Make a contact sheet, one frame every 10 s (`ffmpeg -i VIDEO -vf "fps=1/10,scale=270:-2,tile=6x4" -frames:v 1 sheet.jpg`), and look at it: is anyone else on screen? Anything private (screens, documents, other people's faces)?
- Choose 45-60 s of their own words (75 s max, 90 s hard cap): a hook line for the cold open (the punchiest line, it plays at the very start AND again in its place), the story, the payoff, their spoken CTA if they recorded one. Cut retakes, "no, wait", false starts and rambles. No income claims, no client or student faces.
- Check every date, price or claim against a live page if they mention one. Prefer no prices on video.

## 2. Script + cut list FIRST (stop here)
- Write the table in `SCRIPT.md`: reel time | their words (with source time) | the graphic for that line. Add the end card, what was left out and why, and any warnings (bad audio, someone else in frame, missing CTA line).
- Paste it inline in plain words and ask: "Build it?" Wait for a yes. They may ask for changes; apply them and show the table again.

## 3. Build (after the yes)
1. **Cut.** Write `cutlist.json` from the chosen lines (`in` ~0.04 s early, `out` ~0.08 s late, `gap` 0.1-0.3 s; split a line at a pause to drop a stumble). `python3 cut.py VIDEO cutlist.json cut.mp4` cuts sound and picture together (lips stay in sync), punches in on every other line, makes it 1080x1920 and fixes iPhone HDR colors.
2. **Check the cut.** `./transcribe.sh cut.mp4` and read the words back: every kept line complete, nothing clipped, no "um" you meant to drop. Fix `cutlist.json` and re-cut until it's clean.
3. **Eyes + face.** `python3 lookaway.py cut.mp4` lists moments they look away from the camera and prints `LAYOUT=low|high` (where the cards go so they never cover the face). Every look-away gets covered by a full-screen `cover(...)` cutaway in the beats (or trimmed from the cut). Viewers should only ever see them talking to the camera.
4. **Beats.** Copy `beats_example.py` to `beats_<name>.py` and write `build(g)` from the word times in `cut-words.json`. Use `g.at('word', after)`, never hard-coded seconds. Ready-made beats: `card`, `old_vs_new`, `tag`, `side_chips`, `checklist`, `point`, `cutaway_message`, `big_number`, `chat`, and `cover` (full-screen: show the REAL thing they name, e.g. an app's logo or a screenshot of a public page, with `image='file.png'`; also covers look-aways).
   The rules that make it look professional:
   - Every graphic shows exactly the words being said that second, enters on that word, leaves when they move on. Nothing decorative.
   - Something changes every 2-3 s.
   - When they name a tool, app or website, show its real logo or a real screenshot (download the logo from the brand's own site or press kit; screenshot public pages with headless Chrome, never anything private).
   - When they say a link or a prompt people must copy, hold it on screen long enough to read (about 1 s per 5 words, at least 3 s); add a short `gap` after that line in the cut to make room.
   - Never cover the face. Use the LAYOUT from step 3.
   - Hook on screen at frame 0, and the same hook comes back later.
5. **Generate.** `LAYOUT=<low|high> python3 gen.py cut.mp4 cut-words.json beats_<name> default` writes `hf-default/`. The end card comes from their saved brand.
6. **Check before rendering.** Inside `hf-default`: `npx --yes hyperframes@0.8.210 check` (fix every error; contrast warnings mid-transition are fine), then `npx --yes hyperframes@0.8.210 snapshot --at <every beat>` and LOOK at the frames: nothing on the face, text readable, logos/screenshots crisp, graphics match the words. Fix and re-check.
7. **Render.** `./finish.sh hf-default cut.mp4 reel.mp4` renders, sets the voice to social loudness (-14 LUFS), adds the free music bed at 6% (their own mp3 as a 4th argument, or `none`), fades in/out and saves `reel-cover.jpg`.

## 4. QA, then hand over
- A 1 fps contact sheet of `reel.mp4`: only them on screen, nothing over the face, all text readable, end card shows their logo and link.
- `python3 lookaway.py reel.mp4` once more: no look-aways left outside the cutaways.
- Re-transcribe `reel.mp4` and compare with the script: every word there, nothing cut off.
- Hand over: the MP4, the cover image, a caption draft in their voice (hook first, the steps or point, the CTA pointing to "link in the first comment", 3-5 hashtags) and the first-comment text with the link. Remind them once: say the main point in the first sentence, end with one line telling people what to do next.

## Add-ons they may type
"brand: <key>", "CTA: <offer + link>", "under 45 seconds", "hook is the line about X", "no music", "no stops" (skip the step 2 pause).
`/reel script [topic]`: write a ~45 s script for them to record instead: one picturable idea per sentence, hook first, their real facts only, ending with a spoken CTA line. Paste it and stop.
