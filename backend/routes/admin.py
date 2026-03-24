"""Admin routes — user management, system statistics."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

admin_bp = Blueprint('admin', __name__)


def _get_db():
    from app import db
    return db


def _require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return (jsonify({'error': 'Admin access only'}), 403)
    return None


@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    err = _require_admin()
    if err:
        return err

    role = request.args.get('role')

    from models.user import UserModel
    user_model = UserModel(_get_db())
    users = user_model.get_all(role=role)

    return jsonify({'users': users}), 200


@admin_bp.route('/users/<user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    err = _require_admin()
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    from models.user import UserModel
    user_model = UserModel(_get_db())

    existing = user_model.get_by_id(user_id)
    if not existing:
        return jsonify({'error': 'User not found'}), 404

    success = user_model.update(user_id, data)
    if not success:
        return jsonify({'error': 'No valid fields to update'}), 400

    updated = user_model.get_by_id(user_id)
    return jsonify({'message': 'User updated', 'user': updated}), 200


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    err = _require_admin()
    if err:
        return err

    from models.user import UserModel
    user_model = UserModel(_get_db())

    existing = user_model.get_by_id(user_id)
    if not existing:
        return jsonify({'error': 'User not found'}), 404

    if existing['role'] == 'admin':
        return jsonify({'error': 'Cannot delete admin users'}), 403

    user_model.delete(user_id)
    return jsonify({'message': 'User deleted'}), 200


@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
def system_stats():
    err = _require_admin()
    if err:
        return err

<<<<<<< HEAD
    try:
        from models.user import UserModel
        from models.assignment import AssignmentModel
        from models.submission import SubmissionModel

        db = _get_db()
        user_model = UserModel(db)
        assignment_model = AssignmentModel(db)
        submission_model = SubmissionModel(db)

        stats = {
            'total_users': user_model.count() or 0,
            'total_students': user_model.count(role='student') or 0,
            'total_faculty': (user_model.count(role='faculty') or 0) + (user_model.count(role='teacher') or 0),
            'total_assignments': assignment_model.count() or 0,
            'total_submissions': submission_model.count() or 0,
            'evaluated_submissions': submission_model.count(status='evaluated') or 0,
            'pending_submissions': submission_model.count(status='pending') or 0,
            'error_submissions': submission_model.count(status='error') or 0,
            'average_similarity': round(submission_model.average_score() or 0.0, 2),
        }
        return jsonify({'stats': stats}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Dashboard error', 'message': str(e)}), 500
=======
    from models.user import UserModel
    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel

    db = _get_db()
    user_model = UserModel(db)
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)

    stats = {
        'total_users': user_model.count(),
        'total_students': user_model.count(role='student'),
        'total_faculty': user_model.count(role='faculty'),
        'total_assignments': assignment_model.count(),
        'total_submissions': submission_model.count(),
        'evaluated_submissions': submission_model.count(status='evaluated'),
        'pending_submissions': submission_model.count(status='pending'),
        'error_submissions': submission_model.count(status='error'),
        'average_similarity': round(submission_model.average_score(), 2),
    }

    return jsonify({'stats': stats}), 200
>>>>>>> beee4f2fb628b3d9f30d5399ae88020785a72bc4


# ---- Assignment Management ----

@admin_bp.route('/assignments', methods=['GET'])
@jwt_required()
def list_all_assignments():
    err = _require_admin()
    if err:
        return err

    faculty_id = request.args.get('faculty_id')

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    from models.user import UserModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)
    user_model = UserModel(db)

    if faculty_id:
        assignments = assignment_model.get_all(faculty_id=faculty_id, active_only=False)
    else:
        assignments = assignment_model.get_all(active_only=False)

    # Enrich with faculty name and submission count
    for a in assignments:
        faculty = user_model.get_by_id(a['faculty_id'])
        a['faculty_name'] = faculty['name'] if faculty else 'Unknown'
        subs = submission_model.get_by_assignment(a['id'])
        a['submission_count'] = len(subs)

    return jsonify({'assignments': assignments}), 200


@admin_bp.route('/assignments/<assignment_id>', methods=['DELETE'])
@jwt_required()
def delete_assignment(assignment_id):
    err = _require_admin()
    if err:
        return err

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)

    existing = assignment_model.get_by_id(assignment_id)
    if not existing:
        return jsonify({'error': 'Assignment not found'}), 404

    # Delete all associated submissions first
    submission_model.delete_by_assignment(assignment_id)
    
    # Delete the assignment
    assignment_model.delete(assignment_id)

    return jsonify({'message': 'Assignment and all associated submissions deleted'}), 200


# ---- Submission Management ----

@admin_bp.route('/submissions', methods=['GET'])
@jwt_required()
def list_all_submissions():
    err = _require_admin()
    if err:
        return err

    status = request.args.get('status')

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel
    from models.user import UserModel

    db = _get_db()
    submission_model = SubmissionModel(db)
    assignment_model = AssignmentModel(db)
    user_model = UserModel(db)

    submissions = submission_model.get_all(status=status)

    # Enrich with student name and assignment title
    for s in submissions:
        student = user_model.get_by_id(s['student_id'])
        s['student_name'] = student['name'] if student else 'Unknown'
        assignment = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment['title'] if assignment else 'Unknown'
        s['total_marks'] = assignment['total_marks'] if assignment else 0

    return jsonify({'submissions': submissions}), 200


@admin_bp.route('/submissions/<submission_id>', methods=['DELETE'])
@jwt_required()
def delete_submission(submission_id):
    err = _require_admin()
    if err:
        return err

    from models.submission import SubmissionModel

    submission_model = SubmissionModel(_get_db())

    existing = submission_model.get_by_id(submission_id)
    if not existing:
        return jsonify({'error': 'Submission not found'}), 404

    submission_model.delete(submission_id)

    return jsonify({'message': 'Submission deleted'}), 200
