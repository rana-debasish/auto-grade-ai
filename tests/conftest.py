import os
import sys

import mongomock
import pymongo
import pytest

os.environ.setdefault('FLASK_DEBUG', '1')
sys.path.insert(0, os.path.abspath('backend'))

# Importing the production app creates indexes and performs recovery. Give tests
# an isolated in-memory Mongo-compatible client before the module is imported.
pymongo.MongoClient = mongomock.MongoClient
import app as app_module


@pytest.fixture
def api():
    app_module.db = mongomock.MongoClient().test_db
    app_module.app.config.update(TESTING=True, JWT_SECRET_KEY='test-secret-key-long-enough-for-hs256')
    return app_module.app.test_client()


@pytest.fixture
def token():
    from flask_jwt_extended import create_access_token

    def make(identity, role):
        with app_module.app.app_context():
            return create_access_token(identity=identity, additional_claims={'role': role})
    return make
