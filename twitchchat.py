#!/bin/env python

import sys
from time import sleep
import requests
import socket
import json
from pyyamlconfig import load_config
from pathlib import Path


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
    body = comment.get('message').get('body')
    author = comment.get('commenter').get('display_name')
    content_offset_seconds = comment.get('content_offset_seconds')
    printed = False
    while not printed:
        offset = get_playback_time(client)
        if offset is not None and content_offset_seconds < offset:
            print(f'{author}: {body}')
            printed = True
        sleep(0.1)

client.close()
