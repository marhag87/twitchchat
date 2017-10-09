#!/bin/env python

# MPV Socket
#import socket
#import json
#from pprint import pprint
#
#client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
#client.connect('/var/tmp/stream_mpv.socket')
#client.send(b'{ "command": ["observe_property", 1, "core-idle"] }\n')
#while True:
#    sock_response = client.recv(4096)
#    message = json.loads(sock_response)
#    pprint(message)


# SocketIO loop
#from socketIO_client import SocketIO
#
#counter = 0
#
#with SocketIO('localhost', 5000) as socketIO:
#    while True:
#        socketIO.send({'body': counter})
#        counter = counter + 1


import socket
from socketIO_client import SocketIO
import asyncio


class Chat:
    def __init__(self):
        self.queue = []
        self.loop = asyncio.get_event_loop()
        self.websocket = SocketIO('localhost', 5000)
        self.mpvsocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.mpvsocket.connect('/var/tmp/stream_mpv.socket')
        self.mpvsocket.send(b'{ "command": ["observe_property", 1, "core-idle"] }\n')
        self.mpvsocketloop()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.websocket.disconnect()

    def add_to_queue(self, delay: int, message: str):
        self.queue.append(
            self.loop.call_later(delay, self._message, message)
        )

    def _message(self, message: str):
        self.websocket.send({'body': f'marhag: {message}'})

    def start_loop(self):
        self.loop.run_forever()
        self.loop.close()

    async def mpvsocketloop(self):
        data = await self.mpvsocket.recv(4096)
        print(data)

chat = Chat()
chat.add_to_queue(1, "test")
chat.start_loop()
