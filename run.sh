#!/bin/bash
cd /home/ec2-user/flashcard/
source venv/bin/activate

# environment variables
export FLASK_APP=flashcard_server.py
export FLASK_ENV=production

flask run --host=0.0.0.0 --port=5000
