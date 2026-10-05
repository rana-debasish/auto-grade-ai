"""Bounded in-process evaluation jobs with persisted, restartable state."""

import gc
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

from config import Config

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=Config.EVALUATION_WORKERS, thread_name_prefix='evaluation')


def _clean_text(text):
    if not text: return ''
    text = re.sub(r'\[.*?ppocr.*?\]|Namespace\(.*?\)', ' ', text)
    text = re.sub(r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', ' ', text)
    text = re.sub(r'[^a-zA-Z0-9\s.,;:!?\'"/()\[\]{}@#$%&*+=<>_-]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _redact_identifiers(text):
    """Remove obvious identity labels before sending extracted text to Gemini."""
    text = re.sub(r'(?im)^\s*(?:student\s+)?name\s*[:#-].*$', '[student name removed]', text)
    text = re.sub(r'(?i)\b(?:roll(?:\s*(?:no|number))?|registration(?:\s*(?:no|number))?|student\s*id)\s*[:#-]?\s*[A-Z0-9/-]{3,}', '[student id removed]', text)
    text = re.sub(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', '[email removed]', text, flags=re.I)
    return text


def run_evaluation_async(app, submission_id, file_path, file_type, assignment, total_marks):
    """Persist queued state and submit the work to the app's bounded executor."""
    from models.submission import SubmissionModel
    from app import db

    model = SubmissionModel(db)
    model.update_job(submission_id, status='queued', stage='uploaded', error='', progress=0,
                     step='Waiting for an evaluation worker', increment_attempts=True)
    try:
        return _executor.submit(_evaluate, app, submission_id, file_path, file_type, assignment, total_marks)
    except Exception as exc:
        logger.exception('Could not enqueue evaluation submission_id=%s', submission_id)
        model.update_job(submission_id, status='failed', error='The evaluation could not be queued. Please retry.')
        return None


def _evaluate(app, submission_id, file_path, file_type, assignment, total_marks):
    from app import db
    from models.submission import SubmissionModel
    from services.image_processing import preprocess_image
    from services.ocr_service import extract_text, extract_text_from_file
    from services.gemini_service import evaluate_with_gemini
    from services.marks_calculator import get_grade
    from config import Config

    submission_model = SubmissionModel(db)
    log = logging.LoggerAdapter(logger, {'submission_id': submission_id})
    with app.app_context():
        started = time.perf_counter()
        try:
            submission_model.update_job(submission_id, status='processing', stage='ocr', progress=5, step='Reading your answer script')
            raw_text = _clean_text(_redact_identifiers(extract_text_from_file(file_path) or ''))
            if not raw_text and file_type in ('png', 'jpg', 'jpeg'):
                submission_model.update_job(submission_id, stage='ocr', progress=20, step='Recognizing handwriting')
                image = preprocess_image(file_path)
                raw_text = _clean_text(_redact_identifiers(extract_text(image) or ''))
                del image
                gc.collect()
            raw_text = raw_text[:Config.MAX_EXTRACTED_CHARS]
            submission_model.update_job(submission_id, stage='scoring', progress=40, step='Comparing answers with the rubric')

            questions = assignment.get('rubric') or assignment.get('questions', [])
            questions = questions[:25]
            if not questions:
                raise ValueError('This assignment has no questions to evaluate.')
            normalized_questions = []
            for index, question in enumerate(questions):
                normalized_questions.append({
                    'q_no': question.get('q_no', index + 1),
                    'question': question.get('question') or question.get('question_text', ''),
                    'question_text': question.get('question') or question.get('question_text', ''),
                    'max_marks': question.get('max_marks', question.get('marks', 0)),
                    'marks': question.get('max_marks', question.get('marks', 0)),
                    'model_answer': question.get('model_answer', ''),
                    'keywords': question.get('keywords', []),
                })
            rubric = assignment.get('marking_scheme') or assignment.get('rubric')
            result = evaluate_with_gemini(raw_text, normalized_questions, file_path=file_path,
                                          file_type=file_type, marking_scheme=rubric)
            ai_questions = _normalize_result(result, normalized_questions)

            question_results = []
            total_obtained = 0.0
            needs_review = len(raw_text.strip()) < Config.MIN_OCR_REVIEW_CHARS
            for index, (question, graded) in enumerate(zip(normalized_questions, ai_questions)):
                max_marks = float(question['max_marks'] or 0)
                marks = float(graded['marks'])
                total_obtained += marks
                needs_review = needs_review or graded['confidence'] < Config.REVIEW_CONFIDENCE_THRESHOLD
                question_results.append({
                    'question_index': index, 'question_num': question['q_no'],
                    'question_text': question['question'], 'extracted_answer': graded.get('extracted_answer', ''),
                    'ai_marks': marks, 'marks_obtained': marks, 'total_marks': max_marks,
                    'similarity_score': marks / max_marks if max_marks else 0,
                    'feedback': graded['feedback'], 'confidence': graded['confidence'],
                    'matched_points': graded['matched_points'], 'missing_points': graded['missing_points'],
                })

            denominator = sum(float(question['max_marks'] or 0) for question in normalized_questions)
            similarity = total_obtained / denominator if denominator else 0
            feedback = result.get('overall_feedback', {}) if isinstance(result, dict) else {}
            if isinstance(feedback, str): feedback = {'reasoning': feedback}
            feedback = dict(feedback)
            feedback.setdefault('grade', get_grade(total_obtained, denominator))
            feedback.setdefault('strengths', result.get('strengths', []) if isinstance(result, dict) else [])
            feedback.setdefault('weaknesses', result.get('weaknesses', []) if isinstance(result, dict) else [])
            feedback.setdefault('suggestions', result.get('suggestions', []) if isinstance(result, dict) else [])
            feedback['similarity_percentage'] = round(similarity * 100, 1)
            feedback['marks_obtained'] = total_obtained
            feedback['total_marks'] = denominator
            canonical = {'total': total_obtained, 'questions': [
                {**graded, 'max_marks': normalized_questions[index]['max_marks']}
                for index, graded in enumerate(ai_questions)
            ], 'overall_feedback': feedback}
            submission_model.update_job(submission_id, stage='feedback', progress=90, step='Writing evaluation feedback')
            extracted = '\n\n'.join(f"Question {row['question_num']}: {row['extracted_answer']}" for row in question_results)
            submission_model.update_evaluation(submission_id, extracted, question_results, similarity,
                                               total_obtained, feedback, canonical,
                                               status='needs_review' if needs_review else 'done')
            log.info('Evaluation finished submission_id=%s status=%s questions=%d latency_ms=%d', submission_id,
                     'needs_review' if needs_review else 'done', len(question_results), int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            message = _friendly_error(exc)
            log.exception('Evaluation failed submission_id=%s', submission_id)
            submission_model.update_job(submission_id, status='failed', stage='feedback', error=message,
                                        step='Evaluation failed')
        finally:
            gc.collect()


def _normalize_result(result, questions):
    if not isinstance(result, dict): raise ValueError('The AI response was not valid JSON. Please retry evaluation.')
    raw_questions = result.get('questions')
    normalized = []
    if isinstance(raw_questions, list):
        by_number = {str(item.get('q_no', index + 1)): item for index, item in enumerate(raw_questions) if isinstance(item, dict)}
        for index, question in enumerate(questions):
            item = by_number.get(str(question['q_no']))
            if item is None: raise ValueError(f"The AI response is missing question {question['q_no']}.")
            normalized.append(_validate_question(item, question, index))
    else:
        answers, marks = result.get('extracted_answers', []), result.get('suggested_marks', [])
        for index, question in enumerate(questions):
            if index >= len(marks): raise ValueError(f"The AI response is missing marks for question {question['q_no']}.")
            normalized.append(_validate_question({
                'q_no': question['q_no'], 'marks': marks[index],
                'feedback': result.get('reasoning', ''), 'confidence': 0.7,
                'extracted_answer': answers[index] if index < len(answers) else '',
            }, question, index))
    return normalized


def _validate_question(item, question, index):
    try: marks = float(item.get('marks', item.get('suggested_marks')))
    except (TypeError, ValueError): raise ValueError(f"The AI response has invalid marks for question {question['q_no']}.")
    maximum = float(question['max_marks'] or 0)
    if not 0 <= marks <= maximum: raise ValueError(f"The AI marks for question {question['q_no']} must be between 0 and {maximum:g}.")
    try: confidence = float(item.get('confidence', 0.7))
    except (TypeError, ValueError): confidence = 0.0
    if not 0 <= confidence <= 1: confidence = 0.0
    return {
        'q_no': question['q_no'], 'marks': marks, 'feedback': str(item.get('feedback', '')),
        'confidence': confidence, 'matched_points': _string_list(item.get('matched_points', item.get('matched_keywords', []))),
        'missing_points': _string_list(item.get('missing_points', item.get('missing_keywords', []))),
        'extracted_answer': str(item.get('extracted_answer', item.get('answer', ''))),
    }


def _string_list(value):
    if isinstance(value, str): return [value] if value else []
    return [str(item) for item in value] if isinstance(value, list) else []


def _friendly_error(exc):
    text = str(exc).strip()
    if 'quota' in text.lower() or '429' in text: return 'The AI service is busy. Please retry in a minute.'
    if 'timeout' in text.lower(): return 'Evaluation timed out. Please retry the submission.'
    return text[:280] or 'Evaluation failed. Please retry the submission.'


def executor():
    """Expose the single process executor for controlled shutdown and diagnostics."""
    return _executor
