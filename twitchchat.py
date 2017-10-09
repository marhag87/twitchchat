#!/bin/env python

import sys
from time import sleep
import requests
import socket
import json
from pyyamlconfig import load_config
from pathlib import Path
from socketIO_client import SocketIO


def get_playback_time(sock):
    try:
        sock.send(b'{ "command": ["get_property", "playback-time"] }\n')
    except BrokenPipeError:
        sys.exit(1)
    try:
        sock_response = sock.recv(4096)
        message = json.loads(sock_response)
    except json.decoder.JSONDecodeError:
        return None
    if message.get('error') == 'success':
        return message.get('data')

home = Path.home()
config = load_config(f'{home}/.config/twitchchat.yaml')
clientid = config.get('clientid')
socket_file = config.get('socket')
try:
    video = sys.argv[1]
except IndexError:
    sys.exit(1)
headers = {'Client-ID': clientid, 'Accept': 'application/vnd.twitchtv.v5+json'}

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    client.connect(socket_file)
except ConnectionRefusedError:
    sys.exit(1)
offset = get_playback_time(client)

url = f'https://api.twitch.tv/v5/videos/{video}/comments?content_offset_seconds={offset}'
response = requests.get(url, headers=headers).json()
comments = response.get('comments')
cursor = response.get('_next')
done = False
with SocketIO('localhost', 5000) as socketIO:
    while comments:
        if len(comments) < 15 and not done:
            url = f'https://api.twitch.tv/v5/videos/{video}/comments?cursor={cursor}'
            response = requests.get(url, headers=headers).json()
            new_comments = response.get('comments')
            if new_comments is None:
                done = True
            else:
                comments.extend(response.get('comments'))
                cursor = response.get('_next')
        comment = comments.pop(0)
        text_body = comment.get('message').get('body')
        author = comment.get('commenter').get('display_name')
        body = ""
        fragments = comment.get('message').get('fragments')
        for fragment in fragments:
            emoticon = fragment.get('emoticon')
            if emoticon is None:
                body = f'{body}<span>{fragment.get("text")}</span>'
            else:
                emoticon_id = emoticon.get('emoticon_id')
                emoticon_text = fragment.get('text')
                body = f'''{body}
                    <div class="tw-tooltip-wrapper inline" data-a-target="emote-name">
                        <img class="chat-line__message--emote" src="https://static-cdn.jtvnw.net/emoticons/v1/{emoticon_id}/1.0" alt="{emoticon_text}">
                        <div class="tw-tooltip tw-tooltip--up tw-tooltip--align-center" data-a-target="tw-tooltip-label" style="margin-bottom: 0.9rem;">
                            {emoticon_text}
                        </div>
                    </div>
                '''
        content_offset_seconds = comment.get('content_offset_seconds')
        printed = False
        while not printed:
            offset = get_playback_time(client)
            if offset is not None and content_offset_seconds < offset:
                socketIO.send(
                    {
                        'body': f'''
<div class="vod-message full-width align-items-start flex flex-nowrap pd-05">
    <div class="vod-message__header flex flex-shrink-0 align-right">
        <div class="tw-tooltip-wrapper inline-flex">
            <button class="vod-message__timestamp mg-r-05 pd-x-05"></button>
        </div>
    </div>
    <div class="full-width ">
        <div class="align-items-start flex flex-nowrap">
            <div class="flex-grow-1">
                <span class="video-chat__message-author" style="color: rgb(210, 210, 210);">{author}</span>
                <div data-test-selector="comment-message-selector" class="video-chat__message inline">
                    <span class="pd-x-05">:</span>
                    <span class="qa-mod-message">
                        {body}
                    </span>
                </div>
            </div>
        </div>
    </div>
</div>'''
                    }
                )
                printed = True
        sleep(0.1)

client.close()
