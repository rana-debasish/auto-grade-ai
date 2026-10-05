"""Backfill additive evaluation fields for documents created by older versions.

Run from the repository root with the configured MONGO_URI and MONGO_DB_NAME:
    python backend/migrations/backfill_submission_results.py
"""
from pymongo import MongoClient
from config import Config


def migrate(collection):
    updated = 0
    for doc in collection.find({}):
        updates = {}
        status = doc.get('status', 'pending')
        ai = doc.get('ai_result')
        if not ai and doc.get('question_results'):
            rows = doc['question_results']
            ai = {
                'total': doc.get('marks_obtained', 0),
                'questions': [{
                    'q_no': row.get('question_num', index + 1),
                    'marks': row.get('ai_marks', row.get('marks_obtained', 0)),
                    'max_marks': row.get('total_marks', 0),
                    'feedback': row.get('feedback', ''),
                    'confidence': row.get('confidence', 1.0),
                    'matched_points': row.get('matched_points', []),
                    'missing_points': row.get('missing_points', []),
                    'extracted_answer': row.get('extracted_answer', ''),
                } for index, row in enumerate(rows)],
                'overall_feedback': doc.get('feedback', {}),
            }
            updates['ai_result'] = ai
        if ai and not doc.get('final_result'):
            updates['final_result'] = ai
        if status in ('evaluated', 'done') or ai:
            updates.update(status='done', stage='feedback', reviewed=doc.get('reviewed', doc.get('faculty_reviewed', False)))
        elif status in ('error',):
            updates.update(status='failed', error=doc.get('error_message', ''))
        elif status in ('pending',):
            updates.update(status='queued', stage='uploaded')
        if updates:
            collection.update_one({'_id': doc['_id']}, {'$set': updates})
            updated += 1
    return updated


if __name__ == '__main__':
    with MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000) as client:
        count = migrate(client[Config.MONGO_DB_NAME]['submissions'])
        print(f'Updated {count} submission document(s).')
