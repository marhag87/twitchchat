#!/bin/env python

from flask import (
    Flask,
    render_template,
)
from flask_socketio import (
    SocketIO,
    send,
)

app = Flask(__name__)
socketio = SocketIO(app)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('message')
def handle_message(json):
    send(
        {
            'author': json.get('author'),
            'body': json.get('body'),
        },
        broadcast=True,
    )
