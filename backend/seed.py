"""Seed script — creates the initial admin user in MongoDB."""

import os
import sys
from datetime import datetime, timezone

import bcrypt
from pymongo import MongoClient

# Allow running from project root or backend/
sys.path.insert(0, os.path.dirname(__file__))
from config import Config

# Use TLS/SSL settings only if not on localhost
mongo_kwargs = {
    'serverSelectionTimeoutMS': 5000
}

if "localhost" not in Config.MONGO_URI and "127.0.0.1" not in Config.MONGO_URI:
    mongo_kwargs['tls'] = True
    mongo_kwargs['tlsAllowInvalidCertificates'] = True

client = MongoClient(Config.MONGO_URI, **mongo_kwargs)
db = client[Config.MONGO_DB_NAME]


def seed_admin():
    existing = db.users.find_one({'email': 'admin@system.com'})
    if existing:
        print('[seed] Admin user already exists — skipping.')
        return

    hashed_pw = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())

    admin = {
        'name': 'System Admin',
        'email': 'admin@system.com',
        'password': hashed_pw.decode('utf-8'),
        'role': 'admin',
        'created_at': datetime.now(timezone.utc),
        'is_active': True,
    }

    db.users.insert_one(admin)
    print('[seed] Admin user created successfully.')
    print('       Email   : admin@system.com')
    print('       Password: admin123')


if __name__ == '__main__':
    seed_admin()
    client.close()
