---
name: remix
description: Show What You Say remix. Use when the user types /remix, or asks to copy the edit, rhythm or style of a reel they like with their own photos, product shots or clips ("make this edit with my photos", "same cuts as this video", "turn these 5 photos into a reel like this one"). Reads the reference edit's cuts, beats, camera moves and transitions, then rebuilds it in the Signature look with the user's subjects, a hook word, a payoff scene and a CTA end card. Free and local.
argument-hint: "[reference video or preset] [photos/clips] [brand key] [hook → payoff words]"
---

# /remix: rebuild any edit with your own photos

Input: `$ARGUMENTS`. Expected: a reference (a video file, or a preset: `hype`, `cinematic`, `reveal`, `story`), 1-8 subjects (photos, cutout PNGs, short clips), the brand (a key in `synced/brands.json`) and, optionally, the words. Ask only if there are no subjects. Load the `hyperframes` skill before building. The kit lives where the user cloned it (default `~/show-what-you-say`), this tool in `remix/`.

## What it copies, what it doesn't
- Copies the reference's **structure**: when each cut lands, the tempo and beats, the camera move inside each shot (push in, pull out, pan, tilt, handheld), and how each shot arrives (hard cut, white flash, dip to black, whip).
- Never copies the reference's frames, people or graphics. Its sound is used only if the user says they have the rights to it (their own video, a licensed track); otherwise use their own music.
- It does not generate new AI footage (making the user's face act out someone else's moves). Say so plainly if asked; the free route is their own clips or photos moving to the reference's rhythm.
- A link (Instagram, TikTok, YouTube) is not a file: ask the user to save the video to their Mac and give the path. Don't download from social platforms.

## 1. Read the reference (or pick a preset)
- `cd remix && python3 analyze.py REF.mp4` writes `REF.plan.json` and prints shots, average shot length, BPM and transitions. `--threshold 0.2` finds more cuts, `0.45` fewer.
- No reference? Pick a preset: `hype` (128 BPM, beat cuts, flashes, 11 s), `cinematic` (84 BPM, one shot a bar, dips, 17 s), `reveal` (112 BPM teaser cuts into a long last shot for the payoff, 9 s), `story` (100 BPM, whips, 15 s).
- Tell the user in two lines what you found ("9 shots, 0.9 s each, 124 BPM, 3 flashes, mostly push-ins") and which subjects go where. Only stop to ask if something looks wrong (1 shot found = raise the sensitivity; 60+ shots in 30 s = lower it).

## 2. Words (optional, Signature look)
- `--hook "Busy."`: one or two words on screen at frame 0, struck out in gold on the second beat. The old way, the problem.
- `--lead "Now you're" --payoff "Booked."`: the end scene. A gold shape morphs into the brand colour, the payoff word flips in letter by letter on a beat, rings and sparkles turn, the last photo swings in on a 3D card.
- `--lines "A|B|C"`: one short line per shot after the hook, landing on that shot's first beat. Three words max each.
- Use the user's own words. If they gave none, propose a hook/payoff pair and lines that match the photos, then build.

## 3. Build, check, look
- `python3 remix.py PLAN BRAND photo1.jpg photo2.jpg clip.mov product.png --hook ... --payoff ... --lines ...` (`--no-cta` drops the end card; `--out DIR`).
- A PNG with a transparent background floats on the brand stage (products, a cutout of the user). iPhone HEIC photos convert automatically. Clips play the next stretch of footage in each shot.
- `cd hf-remix-BRAND && npx --yes hyperframes@0.8.210 check`: fix every error except the brand's own gold-on-cream end card title (known, by design).
- `npx --yes hyperframes@0.8.210 snapshot --at` the hook, the middle of 2-3 shots, a transition, the payoff and the end card, and look at them. Faces must not be cut off at the frame edge on a push or pan; if one is, give that photo `still` in the plan or swap its order.

## 4. Finish and hand over
- `./finish.sh hf-remix-BRAND OUT.mp4 MUSIC.mp3` renders, sets the music to -14 LUFS, fades it out and adds the house fade in/out + a cover frame (`OUT-cover.jpg`). Pass the reference itself as the music only with the user's rights to it.
- Hand back the MP4 and the cover. Mention: the clickable link goes in the first comment, not the caption.

## Editing the plan by hand
`PLAN.json` is plain JSON: each shot has `start`, `end`, `move` (`push_in`, `pull_out`, `pan_left`, `pan_right`, `tilt_up`, `tilt_down`, `orbit`, `handheld`, `still`), `strength` 0-1, `energy` and `arrive` (`cut`, `flash`, `dip`, `whip`, `zoom`, `morph`). Change any of them and re-run `remix.py`; save a plan you like into `presets/` to reuse it by name.
