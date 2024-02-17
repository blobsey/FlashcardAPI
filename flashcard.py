from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime, timedelta
from math import exp, pow
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcards.db'
db = SQLAlchemy(app)

# Math constants
w = [0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61]
FACTOR = 19/81
R = 0.9  # Desired retention rate
DECAY = -0.5

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    front = db.Column(db.String, nullable=False)
    back = db.Column(db.String, nullable=False)
    review_date = db.Column(db.Date, default=date.today, nullable=False)
    difficulty = db.Column(db.Float, nullable=True)
    stability = db.Column(db.Float, nullable=True)
    last_review_date = db.Column(db.Date, nullable=True)


    def serialize(self):
        return {
            'id': self.id,
            'front': self.front,
            'back': self.back,
            'review_date': self.review_date.isoformat(),
            'difficulty': self.difficulty if self.difficulty is not None else None,
            'stability': self.stability if self.stability is not None else None,
            'last_review_date': self.last_review_date.isoformat() if self.last_review_date else None
        }   
    

@app.route('/add', methods=['POST'])
def add_flashcard():
    data = request.get_json()
    new_flashcard = Flashcard(front=data['front'], back=data['back'])
    db.session.add(new_flashcard)
    db.session.commit()
    return jsonify({"message": "Flashcard added successfully!"}), 201

@app.route('/list', methods=['GET'])
def get_flashcards():
    flashcards = Flashcard.query.all()
    flashcards_list = [flashcard.serialize() for flashcard in flashcards]
    return jsonify(flashcards_list)

@app.route('/delete/<int:card_id>', methods=['DELETE'])
def delete_flashcard(card_id):
    card = Flashcard.query.get(card_id)
    if not card:
        return jsonify({"message": "Card not found"}), 404

    try:
        db.session.delete(card)
        db.session.commit()
        return jsonify({"message": "Flashcard deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 400

@app.route('/review/<int:card_id>', methods=['POST'])
def review_flashcard(card_id):
    card = Flashcard.query.get(card_id)
    if not card:
        return jsonify({"message": "Card not found"}), 404

    data = request.get_json()
    grade = data.get('grade')
    
    try:
        handle_review(card, grade)
        return jsonify(card.serialize()), 200
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    

def handle_review(card, grade):
    global w, R  # w = weights, R = desired retention rate

    if grade not in [1, 2, 3, 4]:
        raise ValueError("Grade must be between 1 and 4.")

    # Helper function to calculate initial difficulty
    def D0(G):
        return w[4] - (G - 3) * w[5]

    # Calculate difficulty
    if card.difficulty is None:  # First review, use D0()
        card.difficulty = D0(grade)  # Default difficulty
    else:
        # Calculate subsequent difficulty for subsequent reviews
        card.difficulty = (w[7] * D0(3) + (1 - w[7])) * (card.difficulty - w[6] * (grade - 3))

    card.difficulty = max(1, min(card.difficulty, 10)) # Bound between [1, 10] inclusive


    def calculate_new_stability_on_success(D, S, G):
        inner_term = exp(w[8]) * (11 - D) * S**(-w[9]) * (exp(w[10] * (1 - R)) - 1)
        if G == 2: # "Hard" multiplies by .29 
            inner_term *= w[15]
        elif G == 4: # "Easy" multiplies by 2.61
            inner_term *= w[16]
        return S * (inner_term + 1)

    def calculate_new_stability_on_fail(D, S):
        return w[11] * pow(D, (-w[12])) * (pow((S + 1), w[13]) - 1) * exp(w[14] * (1 - R))

    # Calculate stability
    if card.stability is None: # Initial stability
        card.stability = w[grade - 1]  
    elif grade == 1: # Subsequent stability on failure
        card.stability = calculate_new_stability_on_fail(card.difficulty, card.stability)
    else: # Subsequent stability on success
        card.stability = calculate_new_stability_on_success(card.difficulty, card.stability, grade)
    
    # Calculate next review date using FSRS-4.5
    FACTOR = 19/81
    DECAY = -0.5
    I = (card.stability / FACTOR) * (pow(R, 1/DECAY) - 1)  # R is always 0.9 for next review calculation
    next_review_date = datetime.now().date() + timedelta(days=int(I))
    
    # Update the card
    card.review_date = next_review_date
    card.last_review_date = datetime.now().date()
    
    db.session.commit()


@app.route('/next', methods=['GET'])
def get_next_card():
    today = date.today()
    # Query for cards whose review date is today or in the past, sorted by review date
    due_cards = Flashcard.query.filter(Flashcard.review_date <= today).order_by(Flashcard.review_date).all()

    if due_cards:
        # Serialize and return the most overdue card
        return jsonify(due_cards[0].serialize())
    else:
        # No cards are due for review
        return jsonify({"message": "No cards to review right now."}), 200




if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)

