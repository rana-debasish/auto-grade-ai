"""Assignment model — stores assignments created by faculty with model answers."""

from datetime import datetime, timezone

from bson import ObjectId


class AssignmentModel:
    def __init__(self, db):
        self.collection = db['assignments']

    def create(self, faculty_id, title, subject, questions, total_marks=100):
        """
        Create a new assignment.
        
        Args:
            questions: List of { 'question_text': str, 'model_answer': str, 'marks': int }
        """
        assignment = {
            'faculty_id': faculty_id,
            'title': title,
            'subject': subject,
            'questions': questions,
            'total_marks': total_marks,
            'created_at': datetime.now(timezone.utc),
            'is_active': True,
        }
        result = self.collection.insert_one(assignment)
        assignment['_id'] = result.inserted_id
        return self._serialize(assignment)

    def get_by_id(self, assignment_id):
        doc = self.collection.find_one({'_id': ObjectId(assignment_id)})
        return self._serialize(doc) if doc else None

    def get_all(self, faculty_id=None, active_only=True):
        query = {}
        if faculty_id:
            query['faculty_id'] = faculty_id
        if active_only:
            query['is_active'] = True
        docs = self.collection.find(query).sort('created_at', -1)
        return [self._serialize(d) for d in docs]

    def update(self, assignment_id, updates):
        allowed = {'title', 'subject', 'questions', 'total_marks', 'is_active'}
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
            'created_at': doc['created_at'].isoformat(),
            'is_active': doc.get('is_active', True),
        }
