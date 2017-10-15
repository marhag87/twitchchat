#!/bin/bash

source ~/.virtualenvs/twitchchat/bin/activate
i3-msg "workspace ${2-4}; append_layout /home/martin/.i3/moonmoon_workspace.json; exec /bin/google-chrome --app='http://localhost:5000/'; exec streamlink $1 --player='mpv -cache 2048 --x11-name stream --input-unix-socket /var/tmp/stream_mpv.socket' -a '--title ${1##*/} {filename}'" > /dev/null
sleep 2
python ~/git/twitchchat/socketstuff2.py
