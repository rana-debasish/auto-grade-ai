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

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt


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


def _get_semaphore():
    from app import evaluation_semaphore
    return evaluation_semaphore


def _require_student():
    claims = get_jwt()
    if claims.get('role') != 'student':
        return None, (jsonify({'error': 'Student access only'}), 403)
    return get_jwt_identity(), None


def _allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


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
        return jsonify({'error': 'File type not allowed. Use PDF, PNG, JPG, or TXT'}), 400

    # Save file
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Create submission record
    from models.submission import SubmissionModel
    submission_model = SubmissionModel(_get_db())
    submission = submission_model.create(user_id, assignment_id, file_path, ext)
    submission_model.set_status(submission['id'], 'processing', error_message='')
    submission_model.set_progress(submission['id'], 1, 'Queued for evaluation...')

    # Run evaluation pipeline in a background thread so the request returns immediately
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

    if submission['status'] == 'evaluated':
        return jsonify({'message': 'Already evaluated'}), 200

    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    submission_model.set_status(submission_id, 'processing', error_message='')
    submission_model.set_progress(submission_id, 1, 'Queued for re-evaluation...')

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

    submissions = submission_model.get_by_student(user_id)
    # Filter out teacher-uploaded private evaluations
    submissions = [s for s in submissions if not s.get('is_private', False)]

    # Enrich with assignment info
    for s in submissions:
        assignment = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment['title'] if assignment else 'Unknown'
        s['assignment_subject'] = assignment['subject'] if assignment else 'Unknown'
        s['total_marks'] = assignment['total_marks'] if assignment else 0

    return jsonify({'results': submissions}), 200
