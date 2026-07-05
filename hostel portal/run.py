import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Run application on localhost port 5000
    # Enable debug mode for development
    app.run(host='127.0.0.1', port=5000, debug=True)
