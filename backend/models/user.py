"""User model — handles CRUD for students, teachers, and admins."""

from datetime import datetime, timezone

import bcrypt
from bson import ObjectId


class UserModel:
    def __init__(self, db):
        self.collection = db['users']

    def create(self, name, email, password, role='student'):
        """Create a new user with hashed password."""
        if self.collection.find_one({'email': email}):
            return None, 'Email already registered'

        if role not in ('student', 'teacher', 'admin'):
            return None, 'Invalid role'

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        user = {
            'name': name,
            'email': email,
            'password': hashed.decode('utf-8'),
            'role': role,
            'created_at': datetime.now(timezone.utc),
            'is_active': True,
        }

        result = self.collection.insert_one(user)
        user['_id'] = result.inserted_id
        return self._serialize(user), None

    def authenticate(self, email, password):
        """Verify credentials and return user dict or None."""
        user = self.collection.find_one({'email': email})
        if not user:
            return None, 'Invalid email or password'

        if not user.get('is_active', True):
            return None, 'Account is deactivated'

        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return self._serialize(user), None

        return None, 'Invalid email or password'

    def get_by_id(self, user_id):
        user = self.collection.find_one({'_id': ObjectId(user_id)})
        return self._serialize(user) if user else None

    def get_all(self, role=None):
        query = {}
        if role:
            query['role'] = role
        users = self.collection.find(query)
        return [self._serialize(u) for u in users]

    def update(self, user_id, updates):
        """Update user fields (role, is_active, name)."""
        allowed = {'role', 'is_active', 'name'}
        clean = {k: v for k, v in updates.items() if k in allowed}
        if not clean:
            return False
        self.collection.update_one({'_id': ObjectId(user_id)}, {'$set': clean})
        return True

    def delete(self, user_id):
        result = self.collection.delete_one({'_id': ObjectId(user_id)})
        return result.deleted_count > 0

    def count(self, role=None):
        query = {}
        if role:
            query['role'] = role
        return self.collection.count_documents(query)

    @staticmethod
    def _serialize(user):
        """Convert MongoDB document to JSON-safe dict."""
        if not user:
            return None
        return {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'created_at': user['created_at'].isoformat(),
            'is_active': user.get('is_active', True),
        }
