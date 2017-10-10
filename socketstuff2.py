import asyncio
import json
from socketIO_client import SocketIO


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
        self.playback_time = None
        self.messages = [
            {'offset': 185, 'body': 'arrgh'},
            {'offset': 197, 'body': 'blargh'},
        ]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.websocket.disconnect()

    def _message(self, message: str):
        self.websocket.send({'body': f'marhag: {message}'})

    def start(self):
        self.playing_task = loop.create_task(self.print_playing())
        self.playback_time_task = loop.create_task(self.get_play_time())
        loop.create_task(self.queue_messages())

    def stop(self):
        if self.playing_task is not None:
            self.playing_task.cancel()
            self.playback_time_task.cancel()

    async def queue_messages(self):
        while self.playback_time is None:
            await asyncio.sleep(1)
        for message in self.messages:
            pbt = message.get('offset') if self.playback_time is None else self.playback_time
            offset = message.get('offset') - pbt
            body = message.get('body')
            if offset < 0:
                offset = 0
            loop.call_later(
                offset,
                self._message,
                body,
            )
            print(f'created call for "{body}" in {offset}s')

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
            await asyncio.sleep(0.1)
            self._message(self.playback_time)

    async def get_play_time(self):
        while True:
            self.writer.write(b'{ "command": ["get_property", "playback-time"], "request_id": "playback-time" }\n')
            await asyncio.sleep(0.1)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    chat = Chat(loop)
    loop.run_forever()
