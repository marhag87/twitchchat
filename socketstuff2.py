import asyncio
import json
from socketIO_client import SocketIO


class Chat:
    def __init__(self, loop):
        self.loop = loop
        self.reader, self.writer = self.loop.run_until_complete(
            asyncio.open_unix_connection(
                '/var/tmp/stream_mpv.socket',
            )
        )
        self.websocket = SocketIO('localhost', 5000)
        self.writer.write(b'{ "command": ["observe_property", 1, "core-idle"] }\n')
        self.writer.write(b'{ "command": ["get_property", "core-idle"], "request_id": "core-idle" }\n')
        loop.create_task(self.handle_data())
        self.playing_task = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.websocket.disconnect()

    def _message(self, message: str):
        self.websocket.send({'body': f'marhag: {message}'})

    async def handle_data(self):
        while True:
            data = await self.reader.readline()
            message = json.loads(data)
            if message.get('name') == 'core-idle' or message.get('request_id') == 'core-idle':
                playing = not message.get('data')
                if playing:
                    self.playing_task = loop.create_task(self.print_playing())
                else:
                    if self.playing_task is not None:
                        self.playing_task.cancel()
            else:
                print(message)

    async def print_playing(self):
        while True:
            await asyncio.sleep(1)
            self._message("Pickles and stuff")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    chat = Chat(loop)
    loop.run_forever()
