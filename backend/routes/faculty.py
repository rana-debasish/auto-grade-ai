"""Faculty routes — create assignments, view submissions, analytics."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import os

faculty_bp = Blueprint('faculty', __name__)


def _get_db():
    from app import db
    return db


def _require_faculty():
    claims = get_jwt()
    if claims.get('role') != 'faculty' and claims.get('role') != 'teacher': # Allow 'teacher' for backward compatibility during migration
        return None, (jsonify({'error': 'Faculty access only'}), 403)
    return get_jwt_identity(), None


@faculty_bp.route('/assignment', methods=['POST'])
@jwt_required()
def create_assignment():
    user_id, err = _require_faculty()
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    title = data.get('title', '').strip()
    subject = data.get('subject', '').strip()
    full_model_text = data.get('model_answer', '').strip() # Single block of text
    default_total = data.get('total_marks', 100)

    if not title or not subject or not full_model_text:
        return jsonify({'error': 'Title, subject, and model_answer are required'}), 400

    from services.nlp_preprocessing import parse_model_answers
    questions = parse_model_answers(full_model_text, default_total)

    if not questions:
        return jsonify({'error': 'No questions found in text'}), 400

    # Calculate final total marks from parsed questions
    total_marks = sum(q['marks'] for q in questions)

    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    assignment = model.create(user_id, title, subject, questions, total_marks)

    return jsonify({
        'message': f'Assignment created with {len(questions)} questions.',
        'assignment': assignment,
    }), 201


@faculty_bp.route('/evaluation/<submission_id>', methods=['GET'])
@jwt_required()
def get_evaluation_details(submission_id):
    """
    Returns:
    - PDF URL/path
    - model_answers
    - extracted_answers
    - ai_marks
    - max_marks
    """
    user_id, err = _require_faculty()
    if err:
        return err

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel
    
    db = _get_db()
    submission_model = SubmissionModel(db)
    assignment_model = AssignmentModel(db)

    submission = submission_model.get_by_id(submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404

    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    # Extract relevant fields for the new UI
    results = submission.get('question_results', [])
    
    # Map data from results
    # Each result is expected to have {question_index, extracted_answer, similarity_score, marks_obtained, ai_marks}
    
    evaluation_data = {
        'submission_id': submission['id'],
        'student_id': submission['student_id'],
        'assignment_id': submission['assignment_id'],
        'pdf_path': submission.get('file_path'),
        'pdf_url': f"/api/uploads/{os.path.basename(submission.get('file_path'))}" if submission.get('file_path') else None,
        'questions': assignment.get('questions', []), # [{question_text, model_answer, marks}]
        'results': results, # [{extracted_answer, ai_marks, similarity_score}]
        'faculty_marks': submission.get('faculty_marks', {}),
        'faculty_reviewed': submission.get('faculty_reviewed', False),
        'edited_answers': submission.get('edited_answers', {}),
        'faculty_comments': submission.get('faculty_comments', '')
    }

    return jsonify(evaluation_data), 200


@faculty_bp.route('/evaluation/update', methods=['POST'])
@jwt_required()
def update_evaluation():
    """
    Input:
    - submission_id (using submission_id instead of student_id for precision)
    - faculty_marks (JSON/Dict)
    - edited_answers (optional JSON/Dict)
    - faculty_comments (optional)
    """
    user_id, err = _require_faculty()
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    submission_id = data.get('submission_id') or data.get('student_id') # Fallback to student_id if provided
    faculty_marks = data.get('faculty_marks', {})
    edited_answers = data.get('edited_answers', {})
    faculty_comments = data.get('faculty_comments', '')

    if not submission_id:
        return jsonify({'error': 'submission_id is required'}), 400

    from models.submission import SubmissionModel
    db = _get_db()
    submission_model = SubmissionModel(db)

    # Calculate total marks obtained from faculty marks
    total_obtained = 0.0
    if isinstance(faculty_marks, dict):
        for m in faculty_marks.values():
            try:
                total_obtained += float(m)
            except (ValueError, TypeError):
                pass
    elif isinstance(faculty_marks, list):
         for m in faculty_marks:
            try:
                total_obtained += float(m)
            except (ValueError, TypeError):
                pass

    submission_model.update_faculty_marks(submission_id, faculty_marks, edited_answers, faculty_comments)
    
    # Also update total marks_obtained to reflect it in reports
    from bson import ObjectId
    submission_model.collection.update_one(
        {'_id': ObjectId(submission_id)},
        {'$set': {'marks_obtained': total_obtained}}
    )

    return jsonify({'message': 'Evaluation updated successfully', 'total_marks': total_obtained}), 200


@faculty_bp.route('/assignments', methods=['GET'])
@jwt_required()
def list_assignments():
    user_id, err = _require_faculty()
    if err:
        return err

    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    assignments = model.get_all(faculty_id=user_id, active_only=False)

    return jsonify({'assignments': assignments}), 200


@faculty_bp.route('/submissions', methods=['GET'])
@jwt_required()
def view_submissions():
    user_id, err = _require_faculty()
    if err:
        return err

    assignment_id = request.args.get('assignment_id')

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    from models.user import UserModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)
    user_model = UserModel(db)

    if assignment_id:
        # Verify this assignment belongs to the faculty
        assignment = assignment_model.get_by_id(assignment_id)
        if not assignment or assignment['faculty_id'] != user_id:
            return jsonify({'error': 'Assignment not found'}), 404
        submissions = submission_model.get_by_assignment(assignment_id)
    else:
        # Get all submissions for this faculty's assignments
        faculty_assignments = assignment_model.get_all(faculty_id=user_id, active_only=False)
        assignment_ids = [a['id'] for a in faculty_assignments]
        submissions = []
        for aid in assignment_ids:
            submissions.extend(submission_model.get_by_assignment(aid))

    # Enrich with student name and assignment title
    for s in submissions:
        student = user_model.get_by_id(s['student_id'])
        s['student_name'] = student['name'] if student else 'Unknown'
        assignment = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment['title'] if assignment else 'Unknown'
        s['total_marks'] = assignment['total_marks'] if assignment else 0

    return jsonify({'submissions': submissions}), 200


@faculty_bp.route('/reports', methods=['GET'])
@jwt_required()
def reports():
    user_id, err = _require_faculty()
    if err:
        return err

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)

    assignments = assignment_model.get_all(faculty_id=user_id, active_only=False)

    report_data = []
    for a in assignments:
        subs = submission_model.get_by_assignment(a['id'])
        evaluated = [s for s in subs if s['status'] == 'evaluated']

        avg_score = 0.0
        avg_marks = 0.0
        if evaluated:
            avg_score = sum(s['similarity_score'] for s in evaluated) / len(evaluated)
            avg_marks = sum(s['marks_obtained'] for s in evaluated) / len(evaluated)

        report_data.append({
            'assignment_id': a['id'],
            'title': a['title'],
            'subject': a['subject'],
            'total_marks': a['total_marks'],
            'total_submissions': len(subs),
            'evaluated_count': len(evaluated),
            'pending_count': len(subs) - len(evaluated),
            'average_similarity': round(avg_score * 100, 2),
            'average_marks': round(avg_marks, 2),
        })

    return jsonify({'reports': report_data}), 200
