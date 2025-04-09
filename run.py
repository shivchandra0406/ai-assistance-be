from app import create_app
import os
import signal

app, socketio = create_app()

def signal_handler(sig, frame):
    print('Shutting down gracefully...')
    os._exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the app
    socketio.run(
        app,
        debug=True,
        port=5001,
        allow_unsafe_werkzeug=True  # Required for proper WebSocket handling
    )
