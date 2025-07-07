from flask import Blueprint, render_template, current_app
from .extensions import socketio

main_bp = Blueprint('main', __name__, template_folder='templates', static_folder='static')

# --- Routes ---
@main_bp.route('/')
def index() -> str:
    return render_template('index.html')

# --- Socket.IO Events ---
@socketio.on('connect')
def handle_connect() -> None:
    current_app.logger.info('Dashboard client connected')
    socketio.emit('log_message', {'data': 'Real-time connection established.'})

@socketio.on('disconnect')
def handle_disconnect() -> None:
    current_app.logger.info('Dashboard client disconnected')