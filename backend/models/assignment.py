"""Assignment model — stores assignments created by faculty with model answers."""

from datetime import datetime, timezone

from bson import ObjectId


class AssignmentModel:
    def __init__(self, db):
        self.collection = db['assignments']

    def create(self, faculty_id, title, subject, questions, total_marks=100, marking_scheme=None,
               description='', due_date=None, rubric=None, status='published'):
        """
        Create a new assignment.
        """
        assignment = {
            'faculty_id': faculty_id,
            'title': title,
            'subject': subject,
            'questions': questions,
            'total_marks': total_marks,
            'marking_scheme': marking_scheme,
            'description': description,
            'due_date': due_date,
            'rubric': rubric if rubric is not None else [
                {'q_no': index + 1, 'question': q.get('question_text', ''),
                 'max_marks': q.get('marks', 0), 'model_answer': q.get('model_answer', ''),
                 'keywords': q.get('keywords', [])}
                for index, q in enumerate(questions)
            ],
            'status': status,
            'created_at': datetime.now(timezone.utc),
            'is_active': True,
        }
        result = self.collection.insert_one(assignment)
        assignment['_id'] = result.inserted_id
        return self._serialize(assignment)

    def get_by_id(self, assignment_id):
        try:
            doc = self.collection.find_one({'_id': ObjectId(assignment_id)})
        except Exception:
            return None
        return self._serialize(doc) if doc else None

    def get_all(self, faculty_id=None, active_only=True):
        query = {}
        if faculty_id:
            query['faculty_id'] = faculty_id
        if active_only:
            query['is_active'] = True
            query['status'] = {'$in': ['published', None]}
        docs = self.collection.find(query).sort('created_at', -1)
        return [self._serialize(d) for d in docs]

    def update(self, assignment_id, updates):
        allowed = {'title', 'subject', 'questions', 'total_marks', 'is_active', 'description', 'due_date', 'rubric', 'status', 'marking_scheme'}
        clean = {k: v for k, v in updates.items() if k in allowed}
        if not clean:
            return False
        self.collection.update_one({'_id': ObjectId(assignment_id)}, {'$set': clean})
        return True

    def delete(self, assignment_id):
        result = self.collection.delete_one({'_id': ObjectId(assignment_id)})
        return result.deleted_count > 0

    def count(self):
        return self.collection.count_documents({})

    @staticmethod
    def _serialize(doc):
        if not doc:
            return None
        return {
            'id': str(doc['_id']),
            'faculty_id': doc.get('faculty_id') or doc.get('teacher_id'),
            'title': doc['title'],
            'subject': doc['subject'],
            'questions': doc.get('questions', []),
            'total_marks': doc['total_marks'],
            'marking_scheme': doc.get('marking_scheme', ''),
            'description': doc.get('description', ''),
            'due_date': doc.get('due_date'),
            'rubric': doc.get('rubric', []),
            'status': doc.get('status', 'published'),
            'created_at': doc['created_at'].isoformat(),
            'is_active': doc.get('is_active', True),
        }
