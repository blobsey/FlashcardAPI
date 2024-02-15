#/bin/bash
cd /home/ec2-user/flashcard/
source venv/bin/activate

export FLASK_APP=flashcard.py
export FLASK_ENV=production

flask run --host=0.0.0.0
