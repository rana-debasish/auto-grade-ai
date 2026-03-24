"""Authentication routes — register and login."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token

auth_bp = Blueprint('auth', __name__)


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
    token = create_access_token(identity=user['id'], additional_claims={
        'role': user['role'],
        'name': user['name'],
        'email': user['email'],
    })

    return jsonify({
        'message': 'Registration successful',
        'token': token,
        'user': user,
    }), 201


@auth_bp.route('/login', methods=['POST'])
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

    token = create_access_token(identity=user['id'], additional_claims={
        'role': user['role'],
        'name': user['name'],
        'email': user['email'],
    })

    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user,
    }), 200
