from bson import ObjectId
from io import BytesIO

from models.assignment import AssignmentModel
from models.submission import SubmissionModel


def seed_review():
    db = __import__('app').db
    assignment = AssignmentModel(db).create('faculty-1', 'Algebra', 'Math', [
        {'question_text': 'Solve x+1=2', 'marks': 5, 'model_answer': 'x=1'}
    ], 5)
    submission = SubmissionModel(db).create('student-1', assignment['id'], 'script.pdf', 'pdf')
    ai = {'total': 4, 'questions': [{'q_no': 1, 'marks': 4, 'max_marks': 5, 'feedback': 'Good', 'confidence': .9}], 'overall_feedback': {}}
    db.submissions.update_one({'_id': ObjectId(submission['id'])}, {'$set': {'status': 'needs_review', 'ai_result': ai, 'final_result': ai}})
    return assignment, submission, ai


def test_student_cannot_read_another_students_status(api, token):
    _, submission, _ = seed_review()
    response = api.get(f"/api/submissions/{submission['id']}/status", headers={'Authorization': f'Bearer {token("student-2", "student")}'})
    assert response.status_code == 404


def test_owner_can_read_status(api, token):
    _, submission, _ = seed_review()
    response = api.get(f"/api/submissions/{submission['id']}/status", headers={'Authorization': f'Bearer {token("student-1", "student")}'})
    assert response.status_code == 200
    assert response.get_json()['status'] == 'needs_review'


def test_faculty_review_keeps_ai_result_unchanged(api, token):
    assignment, submission, ai = seed_review()
    response = api.put(f"/api/submissions/{submission['id']}/review", json={
        'questions': [{'q_no': 1, 'marks': 3, 'feedback': 'Rechecked'}],
        'overall_feedback': 'Reviewed by faculty',
    }, headers={'Authorization': f'Bearer {token("faculty-1", "faculty")}'})
    assert response.status_code == 200
    saved = SubmissionModel(__import__('app').db).get_by_id(submission['id'])
    assert saved['ai_result'] == ai
    assert saved['final_result']['total'] == 3
    assert saved['reviewed'] is True


def test_submission_detail_hides_path_and_rubric_answers(api, token):
    _, submission, _ = seed_review()
    response = api.get(f"/api/submissions/{submission['id']}", headers={'Authorization': f'Bearer {token("student-1", "student")}'})
    assert response.status_code == 200
    body = response.get_json()['submission']
    assert 'file_path' not in body
    assert 'rubric' not in body['assignment']


def test_role_cannot_access_faculty_analytics(api, token):
    assignment, _, _ = seed_review()
    response = api.get(f"/api/assignments/{assignment['id']}/analytics", headers={'Authorization': f'Bearer {token("student-1", "student")}'})
    assert response.status_code == 404


def test_owner_can_export_assignment_csv(api, token):
    assignment, _, _ = seed_review()
    response = api.get(f"/api/assignments/{assignment['id']}/export.csv", headers={'Authorization': f'Bearer {token("faculty-1", "faculty")}'})
    assert response.status_code == 200
    assert 'text/csv' in response.content_type


def test_student_upload_rejects_a_fake_pdf(api, token, monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config.Config, 'UPLOAD_FOLDER', str(tmp_path))
    assignment = AssignmentModel(__import__('app').db).create('faculty-1', 'Algebra', 'Math', [
        {'question_text': 'Q1', 'marks': 5, 'model_answer': 'answer'}
    ], 5)
    response = api.post('/api/student/submit', data={
        'assignment_id': assignment['id'], 'file': (BytesIO(b'not a PDF'), 'answer.pdf')
    }, headers={'Authorization': f'Bearer {token("student-1", "student")}'}, content_type='multipart/form-data')
    assert response.status_code == 400


def test_refresh_route_accepts_refresh_jwt(api, token):
    refresh = token('student-1', 'student')
    # The refresh endpoint additionally checks that the corresponding active user exists.
    from models.user import UserModel
    import bcrypt
    user_id = __import__('bson').ObjectId()
    __import__('app').db.users.insert_one({'_id': user_id, 'name': 'Test Student', 'email': 'test@example.test', 'role': 'student', 'password': bcrypt.hashpw(b'secret!', bcrypt.gensalt()).decode(), 'is_active': True})
    from flask_jwt_extended import create_refresh_token
    with __import__('app').app.app_context():
        refresh = create_refresh_token(identity=str(user_id), additional_claims={'role': 'student'})
    response = api.post('/api/auth/refresh', headers={'Authorization': f'Bearer {refresh}'})
    assert response.status_code == 200
    assert response.get_json().get('refresh_token')


def test_startup_recovery_requeues_stuck_submission(api, monkeypatch):
    import app as app_module
    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    assignment = AssignmentModel(app_module.db).create('faculty-1', 'Algebra', 'Math', [
        {'question_text': 'Q1', 'marks': 5, 'model_answer': 'answer'}
    ], 5)
    item = SubmissionModel(app_module.db).create('student-1', assignment['id'], 'saved.pdf', 'pdf')
    calls = []
    import services.evaluation_manager as manager
    monkeypatch.setattr(manager, 'run_evaluation_async', lambda *args: calls.append(args))
    with app_module.app.app_context():
        app_module._retry_pending_submissions()
    assert len(calls) == 1


def test_owner_can_retry_failed_submission(api, token, monkeypatch):
    assignment, submission, _ = seed_review()
    db = __import__('app').db
    db.submissions.update_one({'_id': ObjectId(submission['id'])}, {'$set': {'status': 'failed'}})
    import routes.submissions as routes
    monkeypatch.setattr(routes, 'enqueue_retry', lambda *_args: (True, None))
    response = api.post(f"/api/submissions/{submission['id']}/retry", headers={'Authorization': f'Bearer {token("student-1", "student")}'})
    assert response.status_code == 202


def test_admin_can_retry_failed_jobs(api, token, monkeypatch):
    assignment, submission, _ = seed_review()
    db = __import__('app').db
    db.submissions.update_one({'_id': ObjectId(submission['id'])}, {'$set': {'status': 'failed'}})
    import routes.submissions as routes
    monkeypatch.setattr(routes, 'enqueue_retry', lambda *_args: (True, None))
    response = api.post('/api/admin/retry-failed', headers={'Authorization': f'Bearer {token("admin-1", "admin")}'})
    assert response.status_code == 202
    assert response.get_json()['queued'] == 1


def test_flask_serves_ui_and_health(api):
    assert api.get('/').status_code == 200
    assert api.get('/student/submission.html').status_code == 200
    assert api.get('/api/health').get_json()['status'] == 'healthy'
