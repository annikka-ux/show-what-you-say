#!/bin/zsh
# setup.sh : one-time setup on a Mac. Installs the free tools, the whisper model, a free music bed and the
# Claude Code skills. Safe to run again (it also updates the kit's own skills). Nothing here signs in anywhere
# or costs money. When it needs the person at the keyboard (Homebrew asks for the Mac password), it stops and
# prints exactly what to do, then you run it again.
set -e
KIT=${0:A:h}
need() { command -v $1 >/dev/null 2>&1; }
line() { print -r -- "------------------------------------------------------------"; }

# Homebrew lives in /opt/homebrew (Apple silicon) or /usr/local (Intel); Claude's shell may not have it on PATH yet.
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x $b ] && eval "$($b shellenv)" && break; done

if ! xcode-select -p >/dev/null 2>&1; then
  line
  print "ONE STEP FOR YOU: Apple's free developer tools"
  print "A window will pop up asking to install the command line developer tools."
  print "Click Install, then Agree, and wait until it says the software was installed (5 to 15 minutes)."
  print "Then tell Claude: done. Claude runs this setup again."
  line
  xcode-select --install 2>/dev/null || true
  exit 2
fi

if ! need brew; then
  line
  print "ONE STEP FOR YOU: install Homebrew (free, about 5 minutes)"
  print "Claude can't do this part because it needs your Mac password."
  print "1. Open Terminal: press Cmd + Space, type Terminal, press Enter."
  print "2. Paste this line and press Enter:"
  print '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  print "3. Type your Mac password when it asks (you won't see the letters as you type) and press Enter."
  print "   Press Enter again if it asks you to confirm."
  print "4. When it finishes, close Terminal, come back here and tell Claude: done."
  line
  exit 2
fi

need node || brew install node
need ffmpeg || brew install ffmpeg
need whisper-cli || brew install whisper-cpp
need python3 || brew install python

M=$HOME/whisper-models/ggml-medium.bin
if [ ! -s $M ]; then
  mkdir -p ${M:h}
  print "Downloading the speech-to-text model (about 1.5 GB, one time, a good moment for coffee)..."
  curl -L --fail -o $M.part https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin && mv $M.part $M
fi

# A free, confident music bed for the reels (Mixkit Stock Music Free License, mixkit.co/license/#musicFree).
# Downloaded to your Mac only; it is not part of this repo.
mkdir -p $KIT/music
if [ ! -s $KIT/music/default.mp3 ]; then
  curl -L --fail -s -o $KIT/music/default.mp3 https://assets.mixkit.co/music/33/33.mp3 \
    && print "Music bed downloaded: Motivating Mornings (Mixkit free license)" \
    || print "Couldn't download the music bed. Reels will still work; add any mp3 as music/default.mp3 later."
fi

# Skills: the kit's own skills (marked kit: show-what-you-say) are installed and updated; anything else with
# the same name already on this Mac is left alone.
mkdir -p $HOME/.claude/skills
for s in $KIT/skills/*(/); do
  n=${s:t}; dest=$HOME/.claude/skills/$n
  if [ ! -e $dest ]; then cp -R $s $HOME/.claude/skills/; print "installed skill $n"
  elif grep -q 'kit: show-what-you-say' $dest/SKILL.md 2>/dev/null; then rm -rf $dest; cp -R $s $HOME/.claude/skills/; print "updated skill $n"
  else print "skill $n already on this Mac (not from this kit), leaving it as is"; fi
done

npx --yes hyperframes@0.8.210 --version >/dev/null && print "Video renderer OK"
need swift && print "Face and eye check OK" || print "Note: Swift is missing, so the face/eye check is skipped (reels still work)."

line
print "SETUP DONE. ONE LAST STEP FOR YOU:"
print "Quit the Claude app completely (Claude menu > Quit, or Cmd + Q) and open it again."
print "That's how it picks up the new /reel command."
print "Then, in the Code tab, drag in a vertical video of you talking and type: /reel"
print "The first time, Claude asks for your name, logo, colors and link so the reel ends on YOUR brand."
line
