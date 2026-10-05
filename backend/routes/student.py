"""Student routes — view assignments, submit answers, view results.

Optimized for Render free tier (512MB RAM):
- Limited concurrent evaluations via semaphore
- Garbage collection after each evaluation
- Memory-efficient text extraction
"""

import gc
import logging
import os
import uuid
import threading
import time
import mimetypes

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from app import limiter


from config import Config

student_bp = Blueprint('student', __name__)


import re

def clean_ocr_text(text):
    """
    Remove OCR debug logs and noise before storing in database.
    """

    if not text:
        return ""

    # Remove PaddleOCR debug lines
    text = re.sub(r'\[.*?ppocr.*?\]', ' ', text)
    text = re.sub(r'Namespace\(.*?\)', ' ', text)

    # Remove timestamps like 2026/03/11 00:48:38
    text = re.sub(r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', ' ', text)

    # Remove strange characters
    text = re.sub(r'[^a-zA-Z0-9\s.,;:!?\'\"/()\[\]{}@#$%&*+=<>_-]', ' ', text)

    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

def _get_db():
    from app import db
    return db


def _require_student():
    claims = get_jwt()
    if claims.get('role') != 'student':
        return None, (jsonify({'error': 'Student access only'}), 403)
    return get_jwt_identity(), None


def _allowed_file(filename):
    safe = secure_filename(filename or '')
    return '.' in safe and safe.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def _valid_file_signature(file, extension):
    signatures = {
        'pdf': lambda data: data.startswith(b'%PDF-'),
        'png': lambda data: data.startswith(b'\x89PNG\r\n\x1a\n'),
        'jpg': lambda data: data.startswith(b'\xff\xd8\xff'),
        'jpeg': lambda data: data.startswith(b'\xff\xd8\xff'),
    }
    stream = file.stream
    position = stream.tell()
    head = stream.read(16)
    stream.seek(position)
    return signatures[extension](head)


def _upload_user_key():
    try:
        return str(get_jwt_identity())
    except Exception:
        return get_remote_address()


@student_bp.route('/assignments', methods=['GET'])
@jwt_required()
def list_assignments():
    user_id, err = _require_student()
    if err:
        return err

    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    assignments = model.get_all(active_only=True)

    # Don't expose model answers to students
    for a in assignments:
        a.pop('model_answer', None)
        for q in a.get('questions', []):
            q.pop('model_answer', None)

    return jsonify({'assignments': assignments}), 200


@student_bp.route('/submit', methods=['POST'])
@jwt_required()
@limiter.limit(Config.UPLOAD_RATE_LIMIT, key_func=_upload_user_key)
def submit_answer():
    user_id, err = _require_student()
    if err:
        return err

    assignment_id = request.form.get('assignment_id')
    if not assignment_id:
        return jsonify({'error': 'assignment_id is required'}), 400

    # Verify assignment exists
    from models.assignment import AssignmentModel
    assignment_model = AssignmentModel(_get_db())
    assignment = assignment_model.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    # Handle file upload
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use PDF, PNG, or JPG.'}), 400

    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit('.', 1)[1].lower()
    if not _valid_file_signature(file, ext):
        return jsonify({'error': 'The file content does not match its extension. Upload a valid PDF or image.'}), 400
    file.stream.seek(0, os.SEEK_END)
    file_size = file.stream.tell()
    file.stream.seek(0)
    if file_size <= 0:
        return jsonify({'error': 'The uploaded file is empty.'}), 400
    if file_size > Config.MAX_CONTENT_LENGTH:
        return jsonify({'error': 'File exceeds the 10 MB upload limit.'}), 413

    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    file.save(file_path)

    # Create submission record
    from models.submission import SubmissionModel
    submission_model = SubmissionModel(_get_db())
    submission = submission_model.create(user_id, assignment_id, file_path, ext)
    from services.evaluation_manager import run_evaluation_async
    app = current_app._get_current_object()
    run_evaluation_async(
        app, submission['id'], file_path, ext,
        assignment, assignment['total_marks']
    )

    return jsonify({
        'message': 'Answer submitted successfully. Evaluation is in progress.',
        'submission': submission,
    }), 201


@student_bp.route('/retry/<submission_id>', methods=['POST'])
@jwt_required()
def retry_evaluation(submission_id):
    """Retry evaluation for a stuck/errored submission."""
    user_id, err = _require_student()
    if err:
        return err

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel

    db = _get_db()
    submission_model = SubmissionModel(db)
    assignment_model = AssignmentModel(db)

    submission = submission_model.get_by_id(submission_id)
    if not submission or submission['student_id'] != user_id:
        return jsonify({'error': 'Submission not found'}), 404

    if submission['status'] in ('done', 'needs_review'):
        return jsonify({'message': 'Already evaluated'}), 200
    if submission['status'] in ('processing', 'queued'):
        return jsonify({'message': 'Evaluation is already queued or running.', 'status': submission['status']}), 202

    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment or assignment.get('status') == 'draft':
        return jsonify({'error': 'Assignment not found'}), 404

    from services.evaluation_manager import run_evaluation_async
    app = current_app._get_current_object()
    run_evaluation_async(
        app, submission_id, submission['file_path'],
        submission['file_type'], assignment,
        assignment['total_marks']
    )

    return jsonify({'message': 'Re-evaluation started'}), 200


@student_bp.route('/results', methods=['GET'])
@jwt_required()
def view_results():
    user_id, err = _require_student()
    if err:
        return err

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel

    submission_model = SubmissionModel(_get_db())
    assignment_model = AssignmentModel(_get_db())

    try:
        page = max(1, int(request.args['page'])) if 'page' in request.args else None
        page_size = max(1, min(int(request.args.get('page_size', 25)), 100))
    except ValueError:
        return jsonify({'error': 'page and page_size must be integers.'}), 400
    status_filter = request.args.get('status')
    assignment_filter = request.args.get('assignment_id')
    submissions = submission_model.get_by_student(user_id, page, page_size, status_filter, assignment_filter)

    # Enrich with assignment info
    for s in submissions:
        assignment = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment['title'] if assignment else 'Unknown'
        s['assignment_subject'] = assignment['subject'] if assignment else 'Unknown'
        s['total_marks'] = assignment['total_marks'] if assignment else 0

    total = submission_model.count_by_student(user_id, status_filter, assignment_filter)
    return jsonify({'results': submissions, 'pagination': {'page': page or 1, 'page_size': page_size, 'total': total, 'pages': (total + page_size - 1) // page_size}}), 200
