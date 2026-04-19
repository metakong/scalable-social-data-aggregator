from flask import current_app
from .extensions import socketio

@socketio.on('connect')
def handle_connect() -> None:
    current_app.logger.info('Dashboard client connected')
    socketio.emit('log_message', {'data': 'Real-time connection established.'})

@socketio.on('disconnect')
def handle_disconnect() -> None:
    current_app.logger.info('Dashboard client disconnected')