import asyncio
import json
from socketIO_client import SocketIO
import requests
from pyyamlconfig import load_config
from pathlib import Path
from aiohttp import web
import websockets
from sortedcontainers import SortedListWithKey


class Chat:
    def __init__(self, loop):
        self.home = Path.home()
        self.config = load_config(f'{self.home}/.config/twitchchat.yaml')
        self.loop = loop
        self.reader, self.writer = self.loop.run_until_complete(
            asyncio.open_unix_connection(
                self.config.get('socket'),
            )
        )
        self.setup_web()
        socket_server = websockets.serve(self.time, '127.0.0.1', 5001)
        asyncio.get_event_loop().run_until_complete(socket_server)
        self.writer.write(b'{ "command": ["observe_property", 1, "core-idle"] }\n')
        self.writer.write(b'{ "command": ["get_property", "core-idle"], "request_id": "core-idle" }\n')
        self.writer.write(b'{ "command": ["get_property", "title"], "request_id": "title" }\n')
        self.loop.create_task(self.handle_data())
        self.playback_time_task = None
        self.get_messages_task = None
        self.queue_messages_task = None
        self.playback_time = None
        self.cursor = None
        self.fetching_messages = False
        self.messages = SortedListWithKey(key=lambda val: val['offset'])
        self.message_queue = []
        self.clientid = self.config.get('clientid')
        self.headers = {'Client-ID': self.clientid, 'Accept': 'application/vnd.twitchtv.v5+json'}
        self.video = None
        self.last_offset = 0
        self.bttv_emotes = requests.get('https://api.betterttv.net/2/emotes/').json().get('emotes')
        # TODO: Get channel name from api once we have the video string
        channel_emotes = requests.get('https://api.betterttv.net/2/channels/moonmoon_ow').json().get('emotes')
        if channel_emotes is not None:
            self.bttv_emotes.extend(channel_emotes)

    async def _message(self, message: str, message_id: str):
        self.message_queue[:] = [d for d in self.message_queue if d.get('message_id') != message_id]
        return message

    def start(self):
        self.playback_time_task = self.loop.create_task(self.get_play_time())
        self.loop.create_task(self.get_initial_messages())
        self.get_messages_task = self.loop.create_task(self.get_messages_loop())

    def stop(self):
        if self.playback_time_task is not None:
            self.playback_time_task.cancel()
        if self.get_messages_task is not None:
            self.get_messages_task.cancel()
        if self.queue_messages_task is not None:
            self.queue_messages_task.cancel()
        for item in self.message_queue:
            item.get('event').cancel()
        self.message_queue = []

    async def get_initial_messages(self):
        while self.playback_time is None:
            await asyncio.sleep(1)
        await self.get_messages(f'content_offset_seconds={self.playback_time}')

    async def get_messages_loop(self):
        while self.playback_time is None:
            await asyncio.sleep(1)
        while True:
            if self.last_offset - self.playback_time > 10:
                print(f'last_offset: {self.last_offset}, playback_time: {self.playback_time}, diff: {self.last_offset - self.playback_time}, len: {len(self.messages)}')
                sleeptime = self.last_offset - self.playback_time - 9
                print(f'sleeping for {sleeptime}s')
                await asyncio.sleep(sleeptime)
            else:
                await self.get_messages(f'cursor={self.cursor}')

    async def get_messages(self, url):
        if self.fetching_messages:
            return
        self.fetching_messages = True
        while self.video is None:
            await asyncio.sleep(1)
        url = f'https://api.twitch.tv/v5/videos/{self.video}/comments?{url}'
        response = requests.get(url, headers=self.headers).json()
        comments = response.get('comments')
        self.cursor = response.get('_next')
        self.messages.extend(await self.parse_comments(comments))
        self.last_offset = max([x['offset'] for x in self.messages])
        self.fetching_messages = False

    def parse_bttv(self, text):
        for emote in self.bttv_emotes:
            code = emote.get('code')
            text = text.replace(
                code,
                f'<img src="">'
                f'''<div class="tw-tooltip-wrapper inline" data-a-target="emote-name">
                        <img class="chat-line__message--emote" src="https://cdn.betterttv.net/emote/{emote.get("id")}/1x">
                        <div class="tw-tooltip tw-tooltip--up tw-tooltip--align-center" data-a-target="tw-tooltip-label" style="margin-bottom: 0.9rem;">
                            {code}
                        </div>
                    </div>
                '''
            )
        return text

    async def parse_comments(self, comments):
        parsed = []
        for comment in comments:
            fragments = comment.get('message').get('fragments')
            for fragment in fragments:
                emoticon = fragment.get('emoticon')
                if emoticon is None:
                    bttv_parsed = self.parse_bttv(fragment.get('text'))
                    body = f'<span>{bttv_parsed}</span>'
                else:
                    emoticon_id = emoticon.get('emoticon_id')
                    emoticon_text = fragment.get('text')
                    body = f'''<div class="tw-tooltip-wrapper inline" data-a-target="emote-name">
                            <img class="chat-line__message--emote" src="https://static-cdn.jtvnw.net/emoticons/v1/{emoticon_id}/1.0" alt="{emoticon_text}">
                            <div class="tw-tooltip tw-tooltip--up tw-tooltip--align-center" data-a-target="tw-tooltip-label" style="margin-bottom: 0.9rem;">
                                {emoticon_text}
                            </div>
                        </div>
                    '''
            fullbody = f'''
<div class="vod-message full-width align-items-start flex flex-nowrap pd-05">
    <div class="vod-message__header flex flex-shrink-0 align-right">
        <div class="tw-tooltip-wrapper inline-flex">
            <button class="vod-message__timestamp mg-r-05 pd-x-05"></button>
        </div>
    </div>
    <div class="full-width ">
        <div class="align-items-start flex flex-nowrap">
            <div class="flex-grow-1">
                <span class="video-chat__message-author" style="color: rgb(210, 210, 210);">{comment.get('commenter').get('display_name')}</span>
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
            parsed.append({
                'message_id': comment.get('_id'),
                'offset': comment.get('content_offset_seconds'),
                'body': fullbody,
            })
        return parsed

    async def handle_data(self):
        while True:
            data = await self.reader.readline()
            message = json.loads(data)
            name = message.get('name')
            request_id = message.get('request_id')
            if name == 'core-idle' or request_id == 'core-idle':
                playing = not message.get('data')
                if playing:
                    self.start()
                else:
                    self.stop()
            elif request_id == 'playback-time':
                self.playback_time = message.get('data')
            elif request_id == 'title':
                self.video = message.get('data')
            else:
                print(message)

    async def get_play_time(self):
        while True:
            self.writer.write(b'{ "command": ["get_property", "playback-time"], "request_id": "playback-time" }\n')
            await asyncio.sleep(1)

    async def index(self, request):
        return web.Response(
            content_type='text/html',
            text='''<!doctype html>
                <script type="text/javascript" src="http://code.jquery.com/jquery-1.11.1.min.js"></script>
                <script type="text/javascript">
                !function(t){var i=t(window);t.fn.visible=function(t,e,o){if(!(this.length<1)){var r=this.length>1?this.eq(0):this,n=r.get(0),f=i.width(),h=i.height(),o=o?o:"both",l=e===!0?n.offsetWidth*n.offsetHeight:!0;if("function"==typeof n.getBoundingClientRect){var g=n.getBoundingClientRect(),u=g.top>=0&&g.top<h,s=g.bottom>0&&g.bottom<=h,c=g.left>=0&&g.left<f,a=g.right>0&&g.right<=f,v=t?u||s:u&&s,b=t?c||a:c&&a;if("both"===o)return l&&v&&b;if("vertical"===o)return l&&v;if("horizontal"===o)return l&&b}else{var d=i.scrollTop(),p=d+h,w=i.scrollLeft(),m=w+f,y=r.offset(),z=y.top,B=z+r.height(),C=y.left,R=C+r.width(),j=t===!0?B:z,q=t===!0?z:B,H=t===!0?R:C,L=t===!0?C:R;if("both"===o)return!!l&&p>=q&&j>=d&&m>=L&&H>=w;if("vertical"===o)return!!l&&p>=q&&j>=d;if("horizontal"===o)return!!l&&m>=L&&H>=w}}}}(jQuery);
                </script>
                <script type="text/javascript">
                    $(document).ready(function() {
                        var socket = new WebSocket('ws://' + document.domain + ':5001/');

                        socket.onmessage = function(msg) {
                            $("#chatlog").append('<li class="full-width ">' + msg.data + '</li>');
                            while ($('#chatlog li').last().visible() === false) {
                                $('#chatlog li').first().remove();
                            }
                        };
                    });
                </script>
                <link rel="stylesheet" href="https://player.twitch.tv/css/player.css">
                <link rel="stylesheet" href="https://web-cdn.ttvnw.net/styles/application-0fa6ef9268e043c023dfea86aeff7a02.css">
                <link rel="stylesheet" href="https://cdn.betterttv.net/css/betterttv.css?v=7.0.29">
                <link rel="stylesheet" href="https://cdn.betterttv.net/css/betterttv-dark.css?v=7.0.29">
                <link rel="stylesheet" href="https://cdn.betterttv.net/css/betterttv-hide-recommended-channels.css?v=7.0.29">
                <link rel="stylesheet" href="https://web-cdn.ttvnw.net/styles/twilight/core-4a4a70c7c2b9d9ebcbcad1b8c739ad36.css">
                <style>
                    body {
                        overflow:hidden;
                    }
                </style>
                <title>Twitch chat</title>
                <div class=page>
                    <ul id="chatlog" class="full-width align-items-end flex" style="min-height: 0px;"></ul>
                </div>''',
        )

    async def producer(self):
        while self.playback_time is None:
            await asyncio.sleep(1)
        while self.messages:
            return self.messages.pop(0)

    async def time(self, websocket, path):
        while True:
            message = await self.producer()
            if message is not None:
                pbt = message.get('offset') if self.playback_time is None else self.playback_time
                offset = message.get('offset') - pbt
                body = message.get('body')
                if offset < 0:
                    offset = 0
                if offset > 0.2:
                    await asyncio.sleep(offset)
                await websocket.send(body)

    def setup_web(self):
        server = web.Server(self.index)
        self.loop.run_until_complete(
            self.loop.create_server(server, '127.0.0.1', 5000)
        )

if __name__ == '__main__':
    async_loop = asyncio.get_event_loop()
    chat = Chat(async_loop)
    async_loop.run_forever()
