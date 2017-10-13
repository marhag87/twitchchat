import asyncio
import json
from socketIO_client import SocketIO
import requests
from pyyamlconfig import load_config
from pathlib import Path


class Chat:
    def __init__(self, loop):
        self.loop = loop
        self.reader, self.writer = self.loop.run_until_complete(
            asyncio.open_unix_connection(
                '/var/tmp/streamlink.socket',
            )
        )
        self.websocket = SocketIO('localhost', 5000)
        self.writer.write(b'{ "command": ["observe_property", 1, "core-idle"] }\n')
        self.writer.write(b'{ "command": ["get_property", "core-idle"], "request_id": "core-idle" }\n')
        loop.create_task(self.handle_data())
        self.playing_task = None
        self.playback_time_task = None
        self.get_messages_task = None
        self.playback_time = None
        self.cursor = None
        self.fetching_messages = False
        self.messages = []
        self.home = Path.home()
        self.config = load_config(f'{self.home}/.config/twitchchat.yaml')
        self.clientid = self.config.get('clientid')
        self.headers = {'Client-ID': self.clientid, 'Accept': 'application/vnd.twitchtv.v5+json'}
        self.video = '181656394'
        self.last_offset = 0

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.websocket.disconnect()

    def _message(self, message: str):
        self.websocket.send({'body': message})

    def start(self):
        self.playing_task = loop.create_task(self.print_playing())
        self.playback_time_task = loop.create_task(self.get_play_time())
        loop.create_task(self.queue_messages())
        loop.create_task(self.get_initial_messages())
        loop.create_task(self.get_initial_messages())
        self.get_messages_task = loop.create_task(self.get_messages_loop())

    def stop(self):
        if self.playing_task is not None:
            self.playing_task.cancel()
            self.playback_time_task.cancel()
            self.get_messages_task.cancel()

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
                await asyncio.sleep(5)
            else:
                await self.get_messages(f'cursor={self.cursor}')

    async def get_messages(self, url):
        if self.fetching_messages:
            return
        self.fetching_messages = True
        url = f'https://api.twitch.tv/v5/videos/{self.video}/comments?{url}'
        response = requests.get(url, headers=self.headers).json()
        comments = response.get('comments')
        self.cursor = response.get('_next')
        print(response)
        print(url)
        print(self.playback_time)
        self.messages.extend(await self.parse_comments(comments))
        self.last_offset = max([x['offset'] for x in self.messages])
        await self.queue_messages()
        self.fetching_messages = False

    @staticmethod
    async def parse_comments(comments):
        parsed = []
        for comment in comments:
            parsed.append({
                'offset': comment.get('content_offset_seconds'),
                'commenter': comment.get('commenter').get('display_name'),
                'body': comment.get('message').get('body'),
            })
        return parsed

    async def queue_messages(self):
        while self.playback_time is None:
            await asyncio.sleep(1)
        while self.messages:
            message = self.messages.pop()
            pbt = message.get('offset') if self.playback_time is None else self.playback_time
            offset = message.get('offset') - pbt
            commenter = message.get('commenter')
            body = message.get('body')
            if offset < 0:
                offset = 0
            loop.call_later(
                offset,
                self._message,
                f'{commenter}: {body}',
            )
            print(f'created call for "{commenter}: {body}" in {offset}s ({self.playback_time})')

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
            else:
                print(message)

    async def print_playing(self):
        while True:
            await asyncio.sleep(1)
            #self._message(self.playback_time)

    async def get_play_time(self):
        while True:
            self.writer.write(b'{ "command": ["get_property", "playback-time"], "request_id": "playback-time" }\n')
            await asyncio.sleep(1)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    chat = Chat(loop)
    loop.run_forever()
