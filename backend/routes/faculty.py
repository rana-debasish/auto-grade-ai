"""Faculty routes — create assignments, view submissions, analytics."""

import csv
import io
import math

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from app import limiter
from config import Config
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
@limiter.limit(Config.UPLOAD_RATE_LIMIT, key_func=lambda: str(get_jwt_identity() or get_remote_address()))
def create_assignment():
    user_id, err = _require_faculty()
    if err:
        return err

    # Support both JSON and Multipart (for files)
    if request.is_json:
        data = request.get_json()
        files = []
    else:
        # data = request.form
        data = request.form.to_dict()
        files = request.files.getlist('student_copies')

    if isinstance(data.get('rubric'), str):
        import json
        try: data['rubric'] = json.loads(data['rubric'])
        except (ValueError, TypeError): return jsonify({'error': 'Rubric must be a valid JSON array.'}), 400

    title = data.get('title', '').strip()
    subject = data.get('subject', '').strip()
    full_model_text = data.get('model_answer', '').strip()
    marking_scheme = data.get('marking_scheme', '').strip() or None
    try: default_total = float(data.get('total_marks', 100) or 0)
    except (TypeError, ValueError): return jsonify({'error': 'Maximum marks must be a number.'}), 400
    if not math.isfinite(default_total) or default_total < 0:
        return jsonify({'error': 'Maximum marks must be a finite positive number.'}), 400
    status = data.get('status', 'published')
    if status not in ('draft', 'published'):
        return jsonify({'error': 'Status must be draft or published.'}), 400

    if not title or not subject:
        return jsonify({'error': 'Title and subject are required.'}), 400

    rubric = data.get('rubric')
    if isinstance(rubric, list):
        try:
            rubric = [{
                'q_no': int(row.get('q_no', index + 1)),
                'question': str(row.get('question', '')).strip(),
                'max_marks': float(row.get('max_marks', 0)),
                'model_answer': str(row.get('model_answer', '')).strip(),
                'keywords': [str(word).strip() for word in row.get('keywords', []) if str(word).strip()],
            } for index, row in enumerate(rubric)]
            if any(not row['question'] or row['max_marks'] <= 0 for row in rubric):
                raise ValueError('Every rubric row needs a question and positive marks.')
        except (TypeError, ValueError, AttributeError) as exc:
            return jsonify({'error': f'Invalid rubric: {exc}'}), 400
        questions = [{'question_text': row['question'], 'model_answer': row['model_answer'], 'marks': row['max_marks'], 'keywords': row['keywords'], 'q_no': row['q_no']} for row in rubric]
        total_marks = sum(row['max_marks'] for row in rubric)
    elif full_model_text:
        from services.nlp_preprocessing import parse_model_answers
        questions = parse_model_answers(full_model_text, default_total or 100)
        total_marks = sum(q['marks'] for q in questions)
        rubric = [{'q_no': index + 1, 'question': q.get('question_text', ''), 'max_marks': q.get('marks', 0),
                   'model_answer': q.get('model_answer', ''), 'keywords': q.get('keywords', [])} for index, q in enumerate(questions)]
    else:
        questions, rubric = [], []
        total_marks = 0

    if status == 'published' and not questions:
        return jsonify({'error': 'A published assignment needs at least one rubric question.'}), 400
    if default_total and questions and default_total != total_marks:
        return jsonify({'error': f'Question marks total {total_marks:g}, but the assignment maximum is {default_total}.'}), 400

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    from app import db
    
    as_model = AssignmentModel(db)
    sub_model = SubmissionModel(db)
    
    assignment = as_model.create(user_id, title, subject, questions, total_marks, marking_scheme,
                                 description=data.get('description', '').strip(), due_date=data.get('due_date') or None,
                                 rubric=rubric, status=status)
    assignment_id = assignment['id']

    # Handle Bulk Student Copies (if any)
    eval_count = 0
    if files:
        from werkzeug.utils import secure_filename
        from routes.student import _allowed_file as allowed_file
        from services.evaluation_manager import run_evaluation_async
        from flask import current_app
        import uuid
        
        upload_folder = Config.UPLOAD_FOLDER
        os.makedirs(upload_folder, exist_ok=True)

        for f in files:
            if f and allowed_file(f.filename):
                # Extract student name from filename
                # e.g. 23rahul.pdf -> 23rahul
                orig_name = secure_filename(f.filename)
                ext = orig_name.rsplit('.', 1)[1].lower()
                from routes.student import _valid_file_signature
                f.stream.seek(0, os.SEEK_END)
                file_size = f.stream.tell()
                f.stream.seek(0)
                if file_size <= 0 or file_size > Config.MAX_CONTENT_LENGTH or not _valid_file_signature(f, ext):
                    continue
                extracted_name = os.path.splitext(orig_name)[0]
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(upload_folder, filename)
                f.save(filepath)
                
                # Create submission (assoc with teacher user_id as 'student_id' for now, or just leave it)
                # Setting student_id to user_id (faculty) but marking is_private=True
                submission = sub_model.create(
                    student_id=user_id, 
                    assignment_id=assignment_id, 
                    file_path=filepath, 
                    file_type=ext,
                    is_private=True,
                    extracted_student_name=extracted_name
                )
                
                # Trigger Evaluation
                app = current_app._get_current_object()
                run_evaluation_async(
                    app, 
                    submission['id'], 
                    filepath, 
                    ext, 
                    assignment, 
                    total_marks
                )
                eval_count += 1

    msg = f"Assignment created with {len(questions)} questions."
    if eval_count > 0:
        msg += f" {eval_count} student copies are being evaluated."

    return jsonify({
        'message': msg,
        'assignment': assignment,
        'evaluations_started': eval_count
    }), 201


@faculty_bp.route('/assignment/<assignment_id>', methods=['PUT'])
@jwt_required()
def update_assignment(assignment_id):
    user_id, err = _require_faculty()
    if err: return err
    data = request.get_json(silent=True) or {}
    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    existing = model.get_by_id(assignment_id)
    if not existing or existing.get('faculty_id') != user_id:
        return jsonify({'error': 'Assignment not found'}), 404
    updates = {key: data[key] for key in ('title', 'subject', 'description', 'due_date', 'status', 'marking_scheme') if key in data}
    if 'rubric' in data:
        rubric = data['rubric']
        if not isinstance(rubric, list): return jsonify({'error': 'Rubric must be a list.'}), 400
        questions = []
        try:
            for index, row in enumerate(rubric):
                max_marks = float(row.get('max_marks', 0))
                question = str(row.get('question', '')).strip()
                if not question or max_marks <= 0: raise ValueError('Every rubric row needs a question and positive marks.')
                q = {'q_no': int(row.get('q_no', index + 1)), 'question': question, 'question_text': question,
                     'max_marks': max_marks, 'marks': max_marks,
                     'model_answer': str(row.get('model_answer', '')).strip(),
                     'keywords': [str(k).strip() for k in row.get('keywords', []) if str(k).strip()]}
                questions.append(q)
        except (ValueError, TypeError, AttributeError) as exc:
            return jsonify({'error': f'Invalid rubric: {exc}'}), 400
        if updates.get('status', existing.get('status')) == 'published' and not questions:
            return jsonify({'error': 'A published assignment needs at least one rubric question.'}), 400
        updates['rubric'] = questions
        updates['questions'] = [{'question_text': q['question'], 'model_answer': q['model_answer'], 'marks': q['max_marks'], 'keywords': q['keywords'], 'q_no': q['q_no']} for q in questions]
        updates['total_marks'] = sum(q['max_marks'] for q in questions)
    if 'status' in updates and updates['status'] not in ('draft', 'published'):
        return jsonify({'error': 'Status must be draft or published.'}), 400
    if not model.update(assignment_id, updates): return jsonify({'error': 'No valid fields to update'}), 400
    return jsonify({'assignment': model.get_by_id(assignment_id)}), 200


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
    if not assignment or assignment.get('faculty_id') != user_id:
        return jsonify({'error': 'Assignment not found'}), 404

    # Extract relevant fields for the new UI
    results = submission.get('question_results', [])
    
    # Map data from results
    # Each result is expected to have {question_index, extracted_answer, similarity_score, marks_obtained, ai_marks}
    
    evaluation_data = {
        'submission_id': submission['id'],
        'student_id': submission['student_id'],
        'assignment_id': submission['assignment_id'],
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
    submission = submission_model.get_by_id(submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404
    from models.assignment import AssignmentModel
    assignment = AssignmentModel(db).get_by_id(submission['assignment_id'])
    if not assignment or assignment.get('faculty_id') != user_id:
        return jsonify({'error': 'Submission not found'}), 404

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

    submission_model.update_faculty_marks(submission_id, faculty_marks, edited_answers, faculty_comments, user_id)

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
    status = request.args.get('status')
    try:
        page = max(1, int(request.args['page'])) if 'page' in request.args else None
        page_size = max(1, min(int(request.args.get('page_size', 25)), 100))
    except ValueError:
        return jsonify({'error': 'page and page_size must be integers.'}), 400

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
        submissions = submission_model.get_all(status=status, assignment_id=assignment_id, page=page, page_size=page_size)
    else:
        # Get all submissions for this faculty's assignments
        faculty_assignments = assignment_model.get_all(faculty_id=user_id, active_only=False)
        assignment_ids = [a['id'] for a in faculty_assignments]
        submissions = [s for aid in assignment_ids for s in submission_model.get_by_assignment(aid) if not status or s['status'] == status]
        if page is not None:
            offset = (page - 1) * page_size
            submissions = submissions[offset:offset + page_size]

    # Enrich with student name and assignment title
    for s in submissions:
        if s.get('is_private') and s.get('extracted_student_name'):
            s['student_name'] = s.get('extracted_student_name')
        else:
            student = user_model.get_by_id(s['student_id'])
            s['student_name'] = student['name'] if student else 'Unknown'
            
        assignment_doc = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment_doc['title'] if assignment_doc else 'Unknown'
        s['total_marks'] = assignment_doc['total_marks'] if assignment_doc else 0

    total = sum(submission_model.count(status, aid) for aid in assignment_ids) if not assignment_id else submission_model.count(status, assignment_id)
    return jsonify({'submissions': submissions, 'pagination': {'page': page or 1, 'page_size': page_size, 'total': total, 'pages': (total + page_size - 1) // page_size}}), 200


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
        evaluated = [s for s in subs if s['status'] in ('done', 'needs_review', 'evaluated')]

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
