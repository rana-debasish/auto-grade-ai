"""Submission persistence, including additive job and human-review state."""

from copy import deepcopy
from datetime import datetime, timezone

from bson import ObjectId


def utcnow():
    return datetime.now(timezone.utc)


def _canonical_status(value):
    return {'pending': 'queued', 'evaluated': 'done', 'error': 'failed'}.get(value, value or 'queued')


def _legacy_status(value):
    return {'queued': 'pending', 'done': 'evaluated', 'failed': 'error', 'needs_review': 'evaluated'}.get(value, value)


class SubmissionModel:
    def __init__(self, db):
        self.collection = db['submissions']

    def create(self, student_id, assignment_id, file_path, file_type, is_private=False, extracted_student_name=None):
        now = utcnow()
        submission = {
            'student_id': student_id, 'assignment_id': assignment_id,
            'file_path': file_path, 'file_type': file_type, 'is_private': is_private,
            'extracted_student_name': extracted_student_name, 'extracted_text': '', 'ocr_text': '',
            'question_results': [], 'similarity_score': 0.0, 'marks_obtained': 0.0, 'feedback': {},
            'status': 'queued', 'stage': 'uploaded', 'error': '', 'error_message': '', 'attempts': 0,
            'progress': 0, 'progress_step': 'Uploaded', 'updated_at': now,
            'started_at': None, 'finished_at': None, 'submitted_at': now, 'evaluated_at': None,
            'ai_result': None, 'final_result': None, 'reviewed': False, 'reviewed_by': None,
            'reviewed_at': None, 'faculty_reviewed': False, 'faculty_marks': {},
            'edited_answers': {}, 'faculty_comments': '',
        }
        result = self.collection.insert_one(submission)
        submission['_id'] = result.inserted_id
        return self._serialize(submission)

    def update_job(self, submission_id, *, status=None, stage=None, error=None, progress=None, step=None, increment_attempts=False):
        update = {'updated_at': utcnow()}
        if status is not None: update['status'] = status
        if stage is not None: update['stage'] = stage
        if error is not None:
            update['error'] = error
            update['error_message'] = error
        if progress is not None: update['progress'] = progress
        if step is not None: update['progress_step'] = step
        if status == 'processing': update['started_at'] = utcnow()
        if status in ('done', 'failed', 'needs_review'):
            update['finished_at'] = utcnow()
            update['evaluated_at'] = update['finished_at'] if status in ('done', 'needs_review') else None
        operation = {'$set': update}
        if increment_attempts: operation['$inc'] = {'attempts': 1}
        self.collection.update_one({'_id': ObjectId(submission_id)}, operation)

    def update_evaluation(self, submission_id, extracted_text, question_results,
                          similarity_score, marks_obtained, feedback, ai_result=None,
                          status='done'):
        questions = ai_result.get('questions', []) if ai_result else [
            {'q_no': row.get('question_num', index + 1), 'marks': row.get('ai_marks', row.get('marks_obtained', 0)),
             'feedback': row.get('feedback', ''), 'confidence': row.get('confidence', 1.0),
             'matched_points': row.get('matched_points', []), 'missing_points': row.get('missing_points', []),
             'extracted_answer': row.get('extracted_answer', '')}
            for index, row in enumerate(question_results)
        ]
        normalized = ai_result or {
            'total': marks_obtained, 'questions': questions,
            'overall_feedback': feedback,
        }
        normalized['total'] = marks_obtained
        normalized['questions'] = questions
        final_result = deepcopy(normalized)
        now = utcnow()
        self.collection.update_one({'_id': ObjectId(submission_id)}, {'$set': {
            'extracted_text': extracted_text, 'ocr_text': extracted_text,
            'question_results': question_results, 'similarity_score': similarity_score,
            'marks_obtained': marks_obtained, 'feedback': feedback,
            'ai_result': normalized, 'final_result': final_result,
            'status': status, 'stage': 'feedback', 'progress': 100,
            'progress_step': 'Review recommended' if status == 'needs_review' else 'Evaluation complete',
            'error': '', 'error_message': '', 'updated_at': now,
            'finished_at': now, 'evaluated_at': now,
        }})

    def update_faculty_review(self, submission_id, faculty_marks, edited_answers=None, faculty_comments='', reviewed_by=None, edited_feedback=None):
        submission = self.get_by_id(submission_id)
        if not submission:
            return False
        ai = deepcopy(submission.get('ai_result') or {'total': submission.get('marks_obtained', 0), 'questions': [], 'overall_feedback': submission.get('feedback', {})})
        final = deepcopy(submission.get('final_result') or ai)
        rows = final.get('questions', [])
        for index, row in enumerate(rows):
            mark = faculty_marks.get(str(index), faculty_marks.get(index, row.get('marks', 0))) if isinstance(faculty_marks, dict) else (faculty_marks[index] if index < len(faculty_marks) else row.get('marks', 0))
            try: mark = max(0.0, min(float(mark), float(row.get('max_marks', row.get('total_marks', mark)))))
            except (TypeError, ValueError): mark = float(row.get('marks', 0) or 0)
            row['marks'] = mark
            row['faculty_marks'] = mark
            if edited_feedback is not None:
                note = edited_feedback.get(str(index), edited_feedback.get(index)) if isinstance(edited_feedback, dict) else None
                if note is not None: row['feedback'] = note
            if edited_answers is not None:
                answer = edited_answers.get(str(index), edited_answers.get(index)) if isinstance(edited_answers, dict) else None
                if answer is not None: row['extracted_answer'] = answer
        try: total = sum(float(row.get('marks', 0) or 0) for row in rows) if rows else sum(float(v) for v in faculty_marks.values()) if isinstance(faculty_marks, dict) else sum(float(v) for v in faculty_marks)
        except (TypeError, ValueError): total = float(submission.get('marks_obtained', 0) or 0)
        final['total'] = total
        if faculty_comments:
            final['overall_feedback'] = deepcopy(final.get('overall_feedback') or {})
            if isinstance(final['overall_feedback'], dict):
                final['overall_feedback']['faculty_comments'] = str(faculty_comments)[:3000]
        now = utcnow()
        self.collection.update_one({'_id': ObjectId(submission_id)}, {'$set': {
            'ai_result': ai, 'final_result': final,
            'faculty_marks': faculty_marks, 'edited_answers': edited_answers or {},
            'faculty_comments': faculty_comments, 'faculty_reviewed': True,
            'reviewed': True, 'reviewed_by': reviewed_by, 'reviewed_at': now,
            'status': 'done', 'marks_obtained': total, 'updated_at': now,
        }})
        return True

    # Kept for callers that still use the original model method.
    def update_faculty_marks(self, submission_id, faculty_marks, edited_answers=None, faculty_comments='', reviewed_by=None):
        return self.update_faculty_review(submission_id, faculty_marks, edited_answers, faculty_comments, reviewed_by)

    def set_status(self, submission_id, status, error_message=None):
        mapped = _canonical_status(status)
        self.update_job(submission_id, status=mapped, error=error_message)

    def set_progress(self, submission_id, progress, step=''):
        stage = self._stage_from_text(step)
        self.update_job(submission_id, progress=progress, step=step, stage=stage)

    @staticmethod
    def _stage_from_text(step):
        text = (step or '').lower()
        if any(word in text for word in ('extract', 'ocr', 'document')): return 'ocr'
        if any(word in text for word in ('analysis', 'score', 'evaluat')): return 'scoring'
        if any(word in text for word in ('feedback', 'saving', 'finaliz')): return 'feedback'
        return 'uploaded'

    def get_by_id(self, submission_id):
        try: doc = self.collection.find_one({'_id': ObjectId(submission_id)})
        except Exception: return None
        return self._serialize(doc) if doc else None

    def get_by_student(self, student_id, page=None, page_size=25, status=None, assignment_id=None):
        query = {'student_id': student_id, 'is_private': {'$ne': True}}
        if status:
            legacy = {'queued': ['queued', 'pending'], 'done': ['done', 'evaluated'], 'failed': ['failed', 'error']}.get(status, [status])
            query['status'] = {'$in': legacy} if len(legacy) > 1 else legacy[0]
        if assignment_id: query['assignment_id'] = assignment_id
        docs = self.collection.find(query).sort('submitted_at', -1)
        if page is not None: docs = docs.skip((max(1, int(page)) - 1) * max(1, min(int(page_size), 100))).limit(max(1, min(int(page_size), 100)))
        return [self._serialize(d) for d in docs]

    def count_by_student(self, student_id, status=None, assignment_id=None):
        query = {'student_id': student_id, 'is_private': {'$ne': True}}
        if status:
            legacy = {'queued': ['queued', 'pending'], 'done': ['done', 'evaluated'], 'failed': ['failed', 'error']}.get(status, [status])
            query['status'] = {'$in': legacy} if len(legacy) > 1 else legacy[0]
        if assignment_id: query['assignment_id'] = assignment_id
        return self.collection.count_documents(query)

    def get_by_assignment(self, assignment_id):
        docs = self.collection.find({'assignment_id': assignment_id}).sort('submitted_at', -1)
        return [self._serialize(d) for d in docs]

    def get_all(self, status=None, assignment_id=None, student_id=None, page=None, page_size=25):
        query = {}
        if status:
            legacy = {'queued': ['queued', 'pending'], 'done': ['done', 'evaluated'], 'failed': ['failed', 'error']}.get(status, [status])
            query['status'] = {'$in': legacy} if len(legacy) > 1 else legacy[0]
        if assignment_id: query['assignment_id'] = assignment_id
        if student_id: query['student_id'] = student_id
        cursor = self.collection.find(query).sort('submitted_at', -1)
        if page is not None: cursor = cursor.skip((max(1, int(page)) - 1) * max(1, min(int(page_size), 100))).limit(max(1, min(int(page_size), 100)))
        return [self._serialize(d) for d in cursor]

    def delete(self, submission_id): return self.collection.delete_one({'_id': ObjectId(submission_id)}).deleted_count > 0
    def delete_by_assignment(self, assignment_id): return self.collection.delete_many({'assignment_id': assignment_id}).deleted_count
    def count(self, status=None, assignment_id=None):
        query = {'assignment_id': assignment_id} if assignment_id else {}
        if not status: return self.collection.count_documents(query)
        legacy = {'queued': ['queued', 'pending'], 'done': ['done', 'evaluated'], 'failed': ['failed', 'error']}.get(status, [status])
        query['status'] = {'$in': legacy} if len(legacy) > 1 else legacy[0]
        return self.collection.count_documents(query)

    def average_score(self, assignment_id=None):
        match = {'status': {'$in': ['done', 'needs_review', 'evaluated']}}
        if assignment_id: match['assignment_id'] = assignment_id
        result = list(self.collection.aggregate([{'$match': match}, {'$group': {'_id': None, 'avg_score': {'$avg': '$similarity_score'}}}]))
        return result[0]['avg_score'] if result and result[0].get('avg_score') is not None else 0.0

    @staticmethod
    def _serialize(doc):
        if not doc: return None
        raw_status = doc.get('status', 'pending')
        status = _canonical_status(raw_status)
        ai = deepcopy(doc.get('ai_result') or {})
        final = deepcopy(doc.get('final_result') or {})
        rows = doc.get('question_results', [])
        if not ai and rows:
            ai = {'total': sum(float(row.get('ai_marks', row.get('marks_obtained', 0)) or 0) for row in rows), 'questions': [
                {'q_no': row.get('question_num', index + 1), 'marks': row.get('ai_marks', row.get('marks_obtained', 0)),
                 'max_marks': row.get('total_marks', 0), 'feedback': row.get('feedback', ''),
                 'confidence': row.get('confidence', 1.0), 'extracted_answer': row.get('extracted_answer', '')}
                for index, row in enumerate(rows)
            ], 'overall_feedback': doc.get('feedback', {})}
        if not final and ai:
            final = deepcopy(ai)
            marks = doc.get('faculty_marks', {})
            if marks:
                for index, row in enumerate(final.get('questions', [])):
                    if str(index) in marks or index in marks: row['marks'] = marks.get(str(index), marks.get(index))
                final['total'] = sum(float(row.get('marks', 0) or 0) for row in final.get('questions', []))
        progress_step = doc.get('progress_step', '')
        stage = doc.get('stage') or (SubmissionModel._stage_from_text(progress_step) if status == 'processing' else 'done' if status in ('done', 'needs_review') else 'uploaded')
        error = doc.get('error', doc.get('error_message', ''))
        result = {
            'id': str(doc.get('_id', '')), 'student_id': doc.get('student_id'), 'assignment_id': doc.get('assignment_id'),
            'is_private': doc.get('is_private', False), 'extracted_student_name': doc.get('extracted_student_name'),
            'file_path': doc.get('file_path', ''), 'file_type': doc.get('file_type', ''),
            'extracted_text': doc.get('extracted_text', doc.get('ocr_text', '')), 'ocr_text': doc.get('ocr_text', doc.get('extracted_text', '')),
            'question_results': rows, 'similarity_score': doc.get('similarity_score', 0.0),
            'marks_obtained': (final.get('total') if final else doc.get('marks_obtained', 0.0)),
            'feedback': doc.get('feedback', {}), 'status': status, 'legacy_status': _legacy_status(status),
            'stage': stage, 'error': error, 'error_message': error, 'attempts': doc.get('attempts', 0),
            'progress': doc.get('progress', 0), 'progress_step': progress_step,
            'updated_at': doc.get('updated_at').isoformat() if doc.get('updated_at') else None,
            'started_at': doc.get('started_at').isoformat() if doc.get('started_at') else None,
            'finished_at': doc.get('finished_at', doc.get('evaluated_at')).isoformat() if doc.get('finished_at', doc.get('evaluated_at')) else None,
            'submitted_at': doc['submitted_at'].isoformat() if doc.get('submitted_at') else '',
            'evaluated_at': doc['evaluated_at'].isoformat() if doc.get('evaluated_at') else None,
            'ai_result': ai or None, 'final_result': final or None,
            'reviewed': doc.get('reviewed', doc.get('faculty_reviewed', False)),
            'reviewed_by': doc.get('reviewed_by'), 'reviewed_at': doc.get('reviewed_at').isoformat() if doc.get('reviewed_at') else None,
            'faculty_reviewed': doc.get('faculty_reviewed', doc.get('reviewed', False)),
            'faculty_marks': doc.get('faculty_marks', {}), 'edited_answers': doc.get('edited_answers', {}),
            'faculty_comments': doc.get('faculty_comments', ''),
        }
        return result
