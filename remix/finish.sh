#!/bin/zsh
# finish.sh HF_DIR OUT.mp4 [AUDIO] : render the remix, lay the music on (-14 LUFS, faded out at the end),
# then the house fade in/out + cover. AUDIO can be an mp3/wav, or a video whose sound you have the rights to
# (your own past reel, a licensed track). It loops if it is shorter than the remix. No AUDIO = silent video.
set -e
HF=${1:A}; OUT=${2:A}; AUD=${3:+${3:A}}
cd ${0:A:h}
(cd $HF && npx --yes hyperframes@0.8.210 render -o $HF/render.mp4 >/dev/null 2>$HF/render.err) || { print "render failed, see $HF/render.err"; exit 1; }
T=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $HF/render.mp4)
if [ -n "$AUD" ]; then
  FADE=$(echo "$T-2.0" | bc)
  ffmpeg -loglevel error -y -i $HF/render.mp4 -stream_loop -1 -i $AUD -filter_complex \
   "[1:a]atrim=0:${T},asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,afade=t=out:st=${FADE}:d=2.0[a]" \
   -map 0:v -map "[a]" -c:v libx264 -preset slow -crf 20 -profile:v high -r 30 -pix_fmt yuv420p -c:a aac -b:a 192k -ac 2 -movflags +faststart -t ${T} $OUT
else
  ffmpeg -loglevel error -y -i $HF/render.mp4 -f lavfi -i anullsrc=r=48000:cl=stereo \
   -map 0:v -map 1:a -c:v libx264 -preset slow -crf 20 -profile:v high -r 30 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart -t ${T} $OUT
fi
python3 ../synced/fade.py $OUT
