"""Authentication routes — register and login."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required
from app import limiter
from config import Config

auth_bp = Blueprint('auth', __name__)


def _tokens_for_user(user):
    claims = {'role': user['role'], 'name': user['name'], 'email': user['email']}
    return {
        'token': create_access_token(identity=user['id'], additional_claims=claims),
        'refresh_token': create_refresh_token(identity=user['id'], additional_claims=claims),
    }


def _get_db():
    from app import db
    return db


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'student').lower()

    # Validation
    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if role not in ('student', 'faculty', 'teacher'): # Keep teacher for legacy
        return jsonify({'error': 'Role must be student or faculty'}), 400

    from models.user import UserModel
    user_model = UserModel(_get_db())
    user, error = user_model.create(name, email, password, role)

    if error:
        return jsonify({'error': error}), 409

    # Generate JWT token
    tokens = _tokens_for_user(user)

    return jsonify({
        'message': 'Registration successful',
        **tokens,
        'user': user,
    }), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit(Config.LOGIN_RATE_LIMIT)
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    from models.user import UserModel
    user_model = UserModel(_get_db())
    user, error = user_model.authenticate(email, password)

    if error:
        return jsonify({'error': error}), 401

    tokens = _tokens_for_user(user)

    return jsonify({
        'message': 'Login successful',
        **tokens,
        'user': user,
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    from models.user import UserModel
    user = UserModel(_get_db()).get_by_id(get_jwt_identity())
    if not user or not user.get('is_active', True):
        return jsonify({'error': {'code': 'ACCOUNT_INACTIVE', 'message': 'This account is no longer active.'}}), 401
    return jsonify(_tokens_for_user(user)), 200
