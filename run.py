import os
from dotenv import load_dotenv
load_dotenv()

from healthcare import create_app

app = create_app()

if __name__ == '__main__':
    app.run(
        host=os.environ.get('FLASK_HOST', '0.0.0.0'),
        port=int(os.environ.get('FLASK_PORT', 5000)),
        debug=app.config.get('DEBUG', False),
    )
