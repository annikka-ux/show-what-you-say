#!/bin/zsh
# finish.sh HF_DIR VIDEO OUT.mp4 [MUSIC.mp3|none] : render the HyperFrames project, then lay the speaker's voice
# back on (-14 LUFS, the social-media loudness), a quiet music bed (6%), and the house fade in/out + cover.
set -e
HF=${1:A}; VID=${2:A}; OUT=${3:A}; MUS=${4:+${4:A}}
# no music given: use the free bed setup.sh downloaded (music/default.mp3); pass "none" for no music
[ -z "$MUS" ] && [ -s ${0:A:h:h}/music/default.mp3 ] && MUS=${0:A:h:h}/music/default.mp3
[ "${4:-}" = "none" ] && MUS=
cd ${0:A:h}
(cd $HF && npx --yes hyperframes@0.8.210 render -o $HF/render.mp4 >/dev/null 2>$HF/render.err) || { print "render failed, see $HF/render.err"; exit 1; }
T=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $HF/render.mp4)
VOICE="[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,apad,atrim=0:${T}"
if [ -n "$MUS" ]; then
  FADE=$(echo "$T-2.5" | bc)
  ffmpeg -loglevel error -y -i $HF/render.mp4 -i $VID -stream_loop -1 -i $MUS -filter_complex \
   "${VOICE}[voice];[2:a]atrim=0:${T},asetpts=PTS-STARTPTS,aresample=48000,volume=0.06,afade=t=in:d=0.8,afade=t=out:st=${FADE}:d=2.5[mus];[voice][mus]amix=inputs=2:duration=first:normalize=0[a]" \
   -map 0:v -map "[a]" -c:v libx264 -preset slow -crf 20 -profile:v high -r 30 -pix_fmt yuv420p -c:a aac -b:a 192k -ac 2 -movflags +faststart -t ${T} $OUT
else
  ffmpeg -loglevel error -y -i $HF/render.mp4 -i $VID -filter_complex "${VOICE}[a]" \
   -map 0:v -map "[a]" -c:v libx264 -preset slow -crf 20 -profile:v high -r 30 -pix_fmt yuv420p -c:a aac -b:a 192k -ac 2 -movflags +faststart -t ${T} $OUT
fi
python3 fade.py $OUT
