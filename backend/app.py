import gc
import os
import sys
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
import certifi
import logging

from flask import Flask, send_from_directory, jsonify, abort
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from pymongo import MongoClient

from config import Config

# ---------------------------------------------------------------------------
# Memory Management for Render Free Tier (512MB)
# ---------------------------------------------------------------------------

def get_memory_usage_mb():
    """Get current memory usage in MB (cross-platform)."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return -1  # psutil not available


def force_gc():
    """Force garbage collection to free memory."""
    gc.collect()


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

# Configure logging
if os.getenv('SILENT_STARTUP') == '1':
    logging.basicConfig(level=logging.WARNING, format='%(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("="*60)
    logging.info("  AI-Based Answer Script Evaluation System")
    logging.info("  Optimized for Render Free Tier (512MB RAM)")
    logging.info("="*60)
    Config.log_config()

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend'),
    static_url_path=''
)
# Keep direct `python backend/app.py` startup and `from app import db` callers
# bound to this same module rather than importing a second app through routes.
sys.modules.setdefault('app', sys.modules[__name__])

# Configuration
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(seconds=Config.JWT_REFRESH_TOKEN_EXPIRES)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['PROPAGATE_EXCEPTIONS'] = True

# Extensions
CORS(app)
jwt = JWTManager(app)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[])

@jwt.expired_token_loader
def expired_jwt(_header, _payload):
    return jsonify({'error': {'code': 'TOKEN_EXPIRED', 'message': 'Your session has expired. Refresh or sign in again.'}}), 401

@jwt.invalid_token_loader
def invalid_jwt(_reason):
    return jsonify({'error': {'code': 'INVALID_TOKEN', 'message': 'The authentication token is invalid.'}}), 401

@jwt.unauthorized_loader
def missing_jwt(_reason):
    return jsonify({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication is required for this action.'}}), 401

# ---------------------------------------------------------------------------
# Database (with connection pooling optimized for low memory)
# ---------------------------------------------------------------------------

# Let MongoDB URI options control TLS. This keeps Docker's internal
# mongodb://mongo:27017 connection plaintext while mongodb+srv or an explicit
# tls=true/ssl=true URI can use TLS with certifi's CA bundle.
mongo_kwargs = {
    'maxPoolSize': 5,
    'minPoolSize': 1,
    'maxIdleTimeMS': 30000,
    'serverSelectionTimeoutMS': 5000,
    'connectTimeoutMS': 5000,
}

mongo_uri_parts = urlsplit(Config.MONGO_URI)
mongo_uri_options = parse_qs(mongo_uri_parts.query)
if mongo_uri_parts.scheme == 'mongodb+srv' or any(
    value.lower() == 'true'
    for option in ('tls', 'ssl')
    for value in mongo_uri_options.get(option, [])
):
    mongo_kwargs['tlsCAFile'] = certifi.where()

mongo_client = MongoClient(Config.MONGO_URI, **mongo_kwargs)
db = mongo_client[Config.MONGO_DB_NAME]

# Create indexes for performance
try:
    db['users'].create_index('email', unique=True)
    db['submissions'].create_index('student_id')
    db['submissions'].create_index('assignment_id')
    db['submissions'].create_index('status')
    db['submissions'].create_index([('assignment_id', 1), ('status', 1)])
    db['assignments'].create_index('faculty_id')
    logging.info("[DB] Indexes ensured on users, submissions, assignments")
except Exception as e:
    logging.warning(f"[DB] Index creation warning: {e}")

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Register Blueprints
# ---------------------------------------------------------------------------

from routes.auth import auth_bp
from routes.student import student_bp
from routes.faculty import faculty_bp
from routes.admin import admin_bp
from routes.submissions import submissions_bp
from routes.assignment_extras import assignment_extras_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(student_bp, url_prefix='/api/student')
app.register_blueprint(faculty_bp, url_prefix='/api/faculty')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(submissions_bp, url_prefix='/api/submissions')
app.register_blueprint(assignment_extras_bp, url_prefix='/api/assignments')


# ---------------------------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------------------------

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health')
def health_check():
    """Health check endpoint for Render."""
    memory_mb = get_memory_usage_mb()
    try:
        mongo_client.admin.command('ping')
        database_status = 'connected'
    except Exception:
        database_status = 'unavailable'
    status = {
        'status': 'healthy' if database_status == 'connected' else 'degraded',
        'database': database_status,
        'memory_mb': round(memory_mb, 1) if memory_mb > 0 else 'unknown',
        'memory_limit_mb': 512,
        'concurrent_eval_limit': Config.EVALUATION_WORKERS,
    }
    
    # Warn if memory is high
    if memory_mb > 400:
        status['warning'] = 'High memory usage'
        force_gc()  # Try to free memory
    
    return jsonify(status), 200 if database_status == 'connected' else 503


@app.route('/api/uploads/<filename>')
@jwt_required()
def serve_upload(filename):
    """Serve an uploaded file only to its student, faculty owner, or admin."""
    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel
    submission = db['submissions'].find_one({'file_path': os.path.join(Config.UPLOAD_FOLDER, filename)})
    if not submission:
        abort(404)
    serialized = SubmissionModel(db)._serialize(submission)
    assignment = AssignmentModel(db).get_by_id(serialized['assignment_id'])
    if not _authorized_file(serialized, assignment):
        abort(404)
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


def _authorized_file(submission, assignment):
    role = get_jwt().get('role')
    actor = get_jwt_identity()
    if role == 'admin': return True
    if role == 'student': return submission.get('student_id') == actor and not submission.get('is_private')
    return role in ('faculty', 'teacher') and assignment and assignment.get('faculty_id') == actor


@app.route('/<path:path>')
def serve_frontend(path):
    """Serve frontend files; fall back to index.html for SPA-style routing."""
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(e):
    return {'error': {'code': 'BAD_REQUEST', 'message': 'The request could not be processed.'}}, 400


@app.errorhandler(401)
def unauthorized(e):
    return {'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication is required for this action.'}}, 401


@app.errorhandler(403)
def forbidden(e):
    return {'error': {'code': 'FORBIDDEN', 'message': 'You do not have permission to perform this action.'}}, 403


@app.errorhandler(404)
def not_found(e):
    return {'error': {'code': 'NOT_FOUND', 'message': 'The requested resource was not found.'}}, 404


@app.errorhandler(413)
def file_too_large(e):
    return {'error': {'code': 'FILE_TOO_LARGE', 'message': f"Maximum file size is {Config.MAX_CONTENT_LENGTH // (1024 * 1024)} MB."}}, 413


@app.errorhandler(429)
def rate_limited(_e):
    return {'error': {'code': 'RATE_LIMITED', 'message': 'Too many requests. Please wait and try again.'}}, 429


@app.errorhandler(500)
def server_error(e):
    return {'error': {'code': 'INTERNAL_ERROR', 'message': 'Something went wrong. Please try again.'}}, 500

# ---------------------------------------------------------------------------
# Auto-evaluate pending/stuck submissions on startup
# ---------------------------------------------------------------------------

def _retry_pending_submissions():
    """Recover queued and interrupted in-process jobs after a restart."""
    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel
    from services.evaluation_manager import run_evaluation_async
    submission_model = SubmissionModel(db)
    assignment_model = AssignmentModel(db)
    recovered = 0
    for document in db['submissions'].find({'status': {'$in': ['queued', 'processing', 'pending']}}):
        submission = submission_model._serialize(document)
        assignment = assignment_model.get_by_id(submission['assignment_id'])
        if not assignment or not submission.get('file_path'):
            submission_model.update_job(submission['id'], status='failed', error='The assignment or uploaded file is no longer available.')
            continue
        run_evaluation_async(app, submission['id'], submission['file_path'], submission['file_type'], assignment, assignment.get('total_marks', 0))
        recovered += 1
    if recovered:
        logging.info('[STARTUP] Re-enqueued %s interrupted evaluation(s).', recovered)
    
    # Force garbage collection after startup
    force_gc()
    logging.info(f"[STARTUP] Memory usage: {get_memory_usage_mb():.1f}MB")


# Only run startup tasks if this is the main process (not gunicorn worker fork)
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not Config.DEBUG:
    try:
        with app.app_context():
            _retry_pending_submissions()
    except Exception:
        # A transient MongoDB outage should not keep the HTTP process down;
        # the next process restart will retry recovery after the database returns.
        logging.exception('[STARTUP] Submission recovery could not reach MongoDB; recovery will run on the next start.')

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    logging.info("=" * 60)
    logging.info("  AI-Based Answer Script Evaluation System")
    logging.info("  Running at http://localhost:5000")
    logging.info("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)
