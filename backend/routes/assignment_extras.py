"""Faculty analytics and CSV export for one assignment."""

import csv
import io

from flask import Blueprint, jsonify, make_response
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

assignment_extras_bp = Blueprint('assignment_extras', __name__)


def _assignment_scope(assignment_id):
    from app import db
    from models.assignment import AssignmentModel
    assignment = AssignmentModel(db).get_by_id(assignment_id)
    claims = get_jwt()
    if not assignment or claims.get('role') not in ('faculty', 'teacher') or assignment.get('faculty_id') != get_jwt_identity():
        return None, None
    from models.submission import SubmissionModel
    from models.user import UserModel
    return assignment, (SubmissionModel(db), UserModel(db))


@assignment_extras_bp.route('/<assignment_id>/analytics', methods=['GET'])
@jwt_required()
def analytics(assignment_id):
    assignment, models = _assignment_scope(assignment_id)
    if not assignment: return jsonify({'error': 'Assignment not found'}), 404
    submissions_model, users_model = models
    submissions = submissions_model.get_by_assignment(assignment_id)
    scored = [s for s in submissions if s.get('status') in ('done', 'needs_review')]
    max_marks = float(assignment.get('total_marks', 0) or 0)
    distribution = [{'range': f'{i * 10}–{(i + 1) * 10}%', 'count': 0} for i in range(10)]
    question_scores = {}
    student_rows = []
    for submission in scored:
        total = float((submission.get('final_result') or {}).get('total', submission.get('marks_obtained', 0)) or 0)
        pct = min(99.999, max(0, total / max_marks * 100)) if max_marks else 0
        distribution[int(pct // 10)]['count'] += 1
        user = users_model.get_by_id(submission['student_id'])
        student_rows.append({'submission_id': submission['id'], 'name': user.get('name') if user else 'Unknown', 'total': total, 'percentage': round(pct, 1)})
        for question in (submission.get('final_result') or {}).get('questions', []):
            key = str(question.get('q_no', '?'))
            row = question_scores.setdefault(key, {'q_no': question.get('q_no'), 'question': question.get('question', question.get('question_text', '')), 'sum': 0.0, 'max': 0.0, 'count': 0})
            row['sum'] += float(question.get('marks', question.get('ai_marks', 0)) or 0)
            row['max'] += float(question.get('max_marks', question.get('total_marks', 0)) or 0)
            row['count'] += 1
    per_question = [{**row, 'average_marks': round(row['sum'] / row['count'], 2) if row['count'] else 0,
                     'average_percentage': round(row['sum'] / row['max'] * 100, 1) if row['max'] else 0}
                    for row in question_scores.values()]
    student_rows.sort(key=lambda row: row['total'])
    return jsonify({
        'assignment_id': assignment_id, 'evaluated_count': len(scored), 'total_count': len(submissions),
        'average_marks': round(sum(row['total'] for row in student_rows) / len(student_rows), 2) if student_rows else 0,
        'score_distribution': distribution, 'per_question': per_question,
        'lowest_scorers': student_rows[:5], 'highest_scorers': list(reversed(student_rows[-5:])),
    }), 200


@assignment_extras_bp.route('/<assignment_id>/export.csv', methods=['GET'])
@jwt_required()
def export_csv(assignment_id):
    assignment, models = _assignment_scope(assignment_id)
    if not assignment: return jsonify({'error': 'Assignment not found'}), 404
    submissions_model, users_model = models
    submissions = submissions_model.get_by_assignment(assignment_id)
    max_questions = max((len((s.get('final_result') or {}).get('questions', [])) for s in submissions), default=0)
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['Roll no / User ID', 'Name'] + [f'Q{i + 1} marks' for i in range(max_questions)] + ['Total', 'Status'])
    for submission in submissions:
        user = users_model.get_by_id(submission['student_id'])
        questions = (submission.get('final_result') or {}).get('questions', [])
        values = [submission['student_id'], user.get('name', 'Unknown') if user else 'Unknown']
        values.extend(question.get('marks', question.get('ai_marks', 0)) for question in questions)
        values.extend([''] * (max_questions - len(questions)))
        values.extend([submission.get('marks_obtained', 0), submission.get('status', '')])
        writer.writerow([("'" + str(value)) if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value for value in values])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="assignment-{assignment_id}.csv"'
    return response
