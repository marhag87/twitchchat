import asyncio
import json
from socketIO_client import SocketIO
import requests
from pyyamlconfig import load_config
from pathlib import Path


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
        self.websocket = SocketIO('localhost', 5000)
        self.writer.write(b'{ "command": ["observe_property", 1, "core-idle"] }\n')
        self.writer.write(b'{ "command": ["get_property", "core-idle"], "request_id": "core-idle" }\n')
        self.writer.write(b'{ "command": ["get_property", "title"], "request_id": "title" }\n')
        loop.create_task(self.handle_data())
        self.playback_time_task = None
        self.get_messages_task = None
        self.queue_messages_task = None
        self.playback_time = None
        self.cursor = None
        self.fetching_messages = False
        self.messages = []
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.websocket.disconnect()

    def _message(self, message: str, message_id: str):
        self.websocket.send({'body': message})
        self.message_queue[:] = [d for d in self.message_queue if d.get('message_id') != message_id]

    def start(self):
        self.playback_time_task = loop.create_task(self.get_play_time())
        self.queue_messages_task = loop.create_task(self.queue_messages())
        loop.create_task(self.get_initial_messages())
        self.get_messages_task = loop.create_task(self.get_messages_loop())

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
                print(f'last_offset: {self.last_offset}, playback_time: {self.playback_time}, diff: {self.last_offset - self.playback_time}, len: {len(self.message_queue)}')
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
        await self.queue_messages()
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

    async def queue_messages(self):
        while self.playback_time is None:
            await asyncio.sleep(1)
        while self.messages:
            message = self.messages.pop()
            pbt = message.get('offset') if self.playback_time is None else self.playback_time
            offset = message.get('offset') - pbt
            body = message.get('body')
            message_id = message.get('message_id')
            if offset < 0:
                offset = 0
            self.message_queue.append(
                {
                    'message_id': message_id,
                    'event': loop.call_later(
                        offset,
                        self._message,
                        f'{body}',
                        message_id,
                    ),
                }
            )
            #print(f'created call for "{commenter}: {body}" in {offset}s ({message.get("offset")})')

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

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    chat = Chat(loop)
    loop.run_forever()
