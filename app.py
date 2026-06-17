from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
from datetime import timedelta

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///bubble_ai.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# ==================== DATABASE MODELS ====================

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    tier = db.Column(db.String(20), default='original')  # 'original' or 'pro'
    account_created = db.Column(db.DateTime, default=db.func.now())
    is_free_pro = db.Column(db.Boolean, default=False)  # For special admin access
    requests_today = db.Column(db.Integer, default=0)
    last_request_date = db.Column(db.Date)
    subscription_active = db.Column(db.Boolean, default=False)
    subscription_expires = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'tier': self.tier,
            'is_free_pro': self.is_free_pro,
            'subscription_active': self.subscription_active
        }

class PaymentRecord(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='SGD')
    payment_method = db.Column(db.String(50), default='DBS')
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    transaction_id = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'currency': self.currency,
            'payment_method': self.payment_method,
            'status': self.status,
            'created_at': str(self.created_at)
        }

class AIRequest(db.Model):
    __tablename__ = 'ai_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_tier = db.Column(db.String(20))
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    response_time_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'response_time_ms': self.response_time_ms,
            'created_at': str(self.created_at)
        }

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    email = data.get('email').lower()
    password = data.get('password')
    
    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 409
    
    try:
        # Create new user
        user = User(email=email, tier='original')
        user.set_password(password)
        
        # Check if this is the special admin account
        if email == os.getenv('ADMIN_EMAIL', 'sumsudean@gmail.com'):
            user.is_free_pro = True
            user.tier = 'pro'
            user.subscription_active = True
        
        db.session.add(user)
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'access_token': access_token
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    email = data.get('email').lower()
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Create JWT token
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': access_token
    }), 200

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user info"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200

# ==================== AI ROUTES ====================

@app.route('/api/ai/ask', methods=['POST'])
@jwt_required()
def ask_ai():
    """Ask the AI a question"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    question = data.get('question')
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    try:
        import time
        start_time = time.time()
        
        # Simulate AI response (replace with actual AI implementation)
        answer = generate_ai_response(question, user.tier)
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Record the request
        ai_request = AIRequest(
            user_id=user_id,
            user_tier=user.tier,
            question=question,
            answer=answer,
            response_time_ms=response_time_ms
        )
        db.session.add(ai_request)
        db.session.commit()
        
        return jsonify({
            'question': question,
            'answer': answer,
            'response_time_ms': response_time_ms,
            'tier': user.tier
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def generate_ai_response(question, tier):
    """
    Generate AI response based on tier
    Pro tier: faster, more detailed
    Original tier: standard response time
    """
    # This is a placeholder - replace with actual OpenAI/AI implementation
    pro_prefix = "[Pro Response - Fast]\n" if tier == 'pro' else "[Original Response]\n"
    
    responses = {
        'what': f"{pro_prefix}That's a great question! The answer depends on context.",
        'how': f"{pro_prefix}Here's how you can approach this: Step 1... Step 2... Step 3...",
        'why': f"{pro_prefix}The reason is: Multiple factors contribute to this...",
        'when': f"{pro_prefix}Timing is important here: Consider these timeframes...",
        'who': f"{pro_prefix}The relevant parties are: Let me break this down...",
    }
    
    question_lower = question.lower()
    for key, response in responses.items():
        if key in question_lower:
            return response
    
    return f"{pro_prefix}I understand your question. Let me provide a comprehensive answer based on current knowledge..."

# ==================== PAYMENT ROUTES ====================

@app.route('/api/payment/upgrade-to-pro', methods=['POST'])
@jwt_required()
def upgrade_to_pro():
    """Upgrade user to Pro tier (DBS payment only)"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.tier == 'pro' and user.subscription_active:
        return jsonify({'error': 'User is already on Pro tier'}), 400
    
    data = request.get_json()
    payment_method = data.get('payment_method', 'DBS')
    
    if payment_method.upper() != 'DBS':
        return jsonify({'error': 'Only DBS payment method is accepted'}), 400
    
    try:
        # Create payment record
        payment = PaymentRecord(
            user_id=user_id,
            amount=10.00,
            currency='SGD',
            payment_method='DBS',
            status='pending'
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'message': 'Payment processing initiated',
            'payment_id': payment.id,
            'amount': 10.00,
            'currency': 'SGD',
            'payment_method': 'DBS',
            'status': 'pending'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/payment/confirm/<int:payment_id>', methods=['POST'])
@jwt_required()
def confirm_payment(payment_id):
    """Confirm payment and activate Pro tier"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    payment = PaymentRecord.query.get(payment_id)
    
    if not payment or payment.user_id != user_id:
        return jsonify({'error': 'Payment not found'}), 404
    
    try:
        # Update payment status
        payment.status = 'completed'
        
        # Update user tier
        user.tier = 'pro'
        user.subscription_active = True
        
        from datetime import datetime, timedelta
        user.subscription_expires = datetime.utcnow() + timedelta(days=30)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment confirmed and Pro tier activated',
            'user': user.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ==================== UTILITY ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['GET'])
def index():
    """Index route"""
    return jsonify({
        'message': 'Welcome to Bubble AI',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth/register, /api/auth/login, /api/auth/me',
            'ai': '/api/ai/ask',
            'payment': '/api/payment/upgrade-to-pro, /api/payment/confirm/<payment_id>'
        }
    }), 200

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ==================== DATABASE INITIALIZATION ====================

def init_db():
    """Initialize database"""
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
