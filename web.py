#!/bin/env python

from flask import (
    Flask,
    render_template,
)
from flask_socketio import (
    SocketIO,
    send,
)
import logging

app = Flask(__name__)
socketio = SocketIO(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('message')
def handle_message(json):
    send(
        {
            'body': json.get('body'),
        },
        broadcast=True,
    )
