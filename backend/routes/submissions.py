"""Owner- and faculty-scoped submission status, retry, and review APIs."""

from datetime import datetime

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

submissions_bp = Blueprint('submissions', __name__)


def _models():
    from app import db
    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    return SubmissionModel(db), AssignmentModel(db)


def _authorized(submission, assignment):
    claims = get_jwt()
    role = claims.get('role')
    actor = get_jwt_identity()
    if role == 'admin': return True
    if role == 'student': return submission.get('student_id') == actor and not submission.get('is_private')
    return role in ('faculty', 'teacher') and assignment and assignment.get('faculty_id') == actor


def _get_submission(submission_id):
    submission_model, assignment_model = _models()
    submission = submission_model.get_by_id(submission_id)
    assignment = assignment_model.get_by_id(submission['assignment_id']) if submission else None
    return submission_model, assignment_model, submission, assignment


@submissions_bp.route('/<submission_id>/status', methods=['GET'])
@jwt_required()
def submission_status(submission_id):
    submission_model, assignment_model, submission, assignment = _get_submission(submission_id)
    if not submission or not _authorized(submission, assignment):
        return jsonify({'error': {'code': 'SUBMISSION_NOT_FOUND', 'message': 'Submission not found.'}}), 404
    return jsonify({key: submission.get(key) for key in ('id', 'status', 'stage', 'error', 'updated_at', 'progress', 'progress_step')}), 200


@submissions_bp.route('/<submission_id>', methods=['GET'])
@jwt_required()
def submission_detail(submission_id):
    submission_model, assignment_model, submission, assignment = _get_submission(submission_id)
    if not submission or not _authorized(submission, assignment):
        return jsonify({'error': {'code': 'SUBMISSION_NOT_FOUND', 'message': 'Submission not found.'}}), 404
    safe_assignment = {key: assignment.get(key) for key in ('id', 'title', 'subject', 'description', 'due_date', 'total_marks', 'status')}
    submission['assignment'] = safe_assignment
    if submission.get('file_path'):
        from pathlib import Path
        submission['file_url'] = '/api/uploads/' + Path(submission['file_path']).name
    # Never expose internal server paths in the browser payload.
    submission.pop('file_path', None)
    return jsonify({'submission': submission}), 200


def enqueue_retry(submission_model, assignment_model, submission):
    from services.evaluation_manager import run_evaluation_async
    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment: return False, 'Assignment no longer exists.'
    if not submission.get('file_path'): return False, 'The submitted file is no longer available.'
    run_evaluation_async(current_app_object(), submission['id'], submission['file_path'],
                         submission['file_type'], assignment, assignment.get('total_marks', 0))
    return True, None


def current_app_object():
    from flask import current_app
    return current_app._get_current_object()


@submissions_bp.route('/<submission_id>/retry', methods=['POST'])
@jwt_required()
def retry_submission(submission_id):
    submission_model, assignment_model, submission, assignment = _get_submission(submission_id)
    if not submission or not _authorized(submission, assignment):
        return jsonify({'error': {'code': 'SUBMISSION_NOT_FOUND', 'message': 'Submission not found.'}}), 404
    if submission['status'] != 'failed':
        return jsonify({'error': {'code': 'NOT_RETRYABLE', 'message': 'Only failed evaluations can be retried.'}}), 409
    ok, error = enqueue_retry(submission_model, assignment_model, submission)
    if not ok: return jsonify({'error': {'code': 'RETRY_UNAVAILABLE', 'message': error}}), 409
    return jsonify({'message': 'Evaluation queued again.', 'status': 'queued'}), 202


@submissions_bp.route('/<submission_id>/review', methods=['PUT'])
@jwt_required()
def review_submission(submission_id):
    role = get_jwt().get('role')
    if role not in ('faculty', 'teacher'):
        return jsonify({'error': {'code': 'FORBIDDEN', 'message': 'Faculty access only.'}}), 403
    submission_model, assignment_model, submission, assignment = _get_submission(submission_id)
    if not submission or not assignment or assignment.get('faculty_id') != get_jwt_identity():
        return jsonify({'error': {'code': 'SUBMISSION_NOT_FOUND', 'message': 'Submission not found.'}}), 404
    data = request.get_json(silent=True) or {}
    items = data.get('questions')
    if not isinstance(items, list):
        return jsonify({'error': {'code': 'INVALID_REVIEW', 'message': 'Provide a questions array with marks and feedback.'}}), 400
    ai_questions = (submission.get('ai_result') or {}).get('questions', [])
    if not ai_questions:
        return jsonify({'error': {'code': 'NOT_EVALUATED', 'message': 'The submission has no AI result to review.'}}), 409
    marks, feedback = {}, {}
    try:
        for item in items:
            index = int(item.get('q_no', 0)) - 1
            if index < 0 or index >= len(ai_questions): raise ValueError('A question number is invalid.')
            maximum = float(ai_questions[index].get('max_marks', ai_questions[index].get('total_marks', 0)))
            value = float(item.get('marks'))
            if not 0 <= value <= maximum: raise ValueError(f'Question {index + 1} marks must be between 0 and {maximum:g}.')
            marks[str(index)] = value
            feedback[str(index)] = str(item.get('feedback', ai_questions[index].get('feedback', '')))[:3000]
    except (ValueError, TypeError) as exc:
        return jsonify({'error': {'code': 'INVALID_REVIEW', 'message': str(exc)}}), 400
    if len(marks) != len(ai_questions):
        return jsonify({'error': {'code': 'INVALID_REVIEW', 'message': 'Include marks and feedback for every question.'}}), 400
    submission_model.update_faculty_review(submission_id, marks, faculty_comments=data.get('overall_feedback', ''),
                                           reviewed_by=get_jwt_identity(), edited_feedback=feedback)
    updated = submission_model.get_by_id(submission_id)
    return jsonify({'message': 'Review saved.', 'reviewed': True, 'final_result': updated['final_result']}), 200
