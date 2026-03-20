"""Student routes — view assignments, submit answers, view results.

Optimized for Render free tier (512MB RAM):
- Limited concurrent evaluations via semaphore
- Garbage collection after each evaluation
- Memory-efficient text extraction
"""

import gc
import logging
import os
import uuid
import threading
import time

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt


from config import Config

student_bp = Blueprint('student', __name__)


import re

def clean_ocr_text(text):
    """
    Remove OCR debug logs and noise before storing in database.
    """

    if not text:
        return ""

    # Remove PaddleOCR debug lines
    text = re.sub(r'\[.*?ppocr.*?\]', ' ', text)
    text = re.sub(r'Namespace\(.*?\)', ' ', text)

    # Remove timestamps like 2026/03/11 00:48:38
    text = re.sub(r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', ' ', text)

    # Remove strange characters
    text = re.sub(r'[^a-zA-Z0-9\s.,;:!?\'\"/()\[\]{}@#$%&*+=<>_-]', ' ', text)

    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

def _get_db():
    from app import db
    return db


def _get_semaphore():
    from app import evaluation_semaphore
    return evaluation_semaphore


def _require_student():
    claims = get_jwt()
    if claims.get('role') != 'student':
        return None, (jsonify({'error': 'Student access only'}), 403)
    return get_jwt_identity(), None


def _allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def _run_evaluation_async(app, submission_id, file_path, ext, assignment, total_marks):

    def _evaluate():

        semaphore = _get_semaphore()

        if not semaphore.acquire(blocking=True, timeout=300):
            print(f"[EVAL] Timeout waiting for semaphore: {submission_id}")
            return

        try:
            with app.app_context():

                from models.submission import SubmissionModel
                submission_model = SubmissionModel(_get_db())

                def _progress(pct, step):
                    submission_model.set_progress(submission_id, pct, step)

                try:
                    from services.image_processing import preprocess_image
                    from services.ocr_service import extract_text, extract_text_from_file
                    from services.nlp_preprocessing import preprocess_text
                    from services.marks_calculator import calculate_marks
                    from services.feedback_generator import generate_feedback
                    from services.nlp_preprocessing import segment_student_answers

                    t_start = time.time()

                    # Create a debug log file in /tmp
                    log_file = f"/tmp/eval_{submission_id}.log"
                    with open(log_file, "w") as f_log:
                        f_log.write(f"Starting evaluation for {submission_id}\n")

                    def _log(msg):
                        with open(log_file, "a") as f_log:
                            f_log.write(f"{msg}\n")
                        print(f"[EVAL-DEBUG] {msg}")

                    _log(f"Project directory: {os.getcwd()}")
                    _log(f"File: {file_path} ({ext})")

                    # ------------------------------------------------
                    # STEP 1: TEXT EXTRACTION
                    # ------------------------------------------------

                    _progress(5, 'Extracting text from document...')
                    raw_text = extract_text_from_file(file_path) or ""

                    # Clean OCR garbage text
                    raw_text = clean_ocr_text(raw_text)

                    # Only run image preprocessing fallback for actual images.
                    if not raw_text and ext in ["png", "jpg", "jpeg"]:

                        print("[EVAL] Direct extraction failed. Running OCR fallback")

                        _progress(10, 'Preprocessing image for OCR...')
                        processed_image = preprocess_image(file_path)

                        _progress(30, 'Performing OCR extraction...')
                        raw_text = extract_text(processed_image) or ""

                        # CLEAN OCR TEXT AFTER FALLBACK
                        raw_text = clean_ocr_text(raw_text)

                        del processed_image
                        gc.collect()

                    if raw_text:
                        raw_text = raw_text[:Config.MAX_EXTRACTED_CHARS]
                    
                    if not raw_text and ext not in ["pdf", "png", "jpg", "jpeg"]:
                        raise ValueError(
                            "No readable text could be extracted from the submitted file. "
                            "Please upload a text-based PDF, DOCX, TXT, or a clearer image."
                        )

                    _progress(60, 'Text extracted')
                    _log(f"Text extracted: {len(raw_text)} chars")

                    # ------------------------------------------------
                    # STEP 2: GEMINI AI EVALUATION
                    # ------------------------------------------------

                    _progress(70, 'AI Analysis in progress...')

                    questions = assignment.get('questions', [])[:25]
                    if not questions:
                        raise ValueError("Assignment has no questions configured for evaluation.")

                    from services.gemini_service import evaluate_with_gemini
                    
                    # Call Gemini with both extracted text (if any) and the file itself
                    gemini_result = evaluate_with_gemini(raw_text, questions, file_path=file_path, file_type=ext)
                    
                    if not gemini_result:
                        # Fallback or error if Gemini fails
                        raise ValueError("AI Evaluation failed. Please try again.")

                    extracted_answers = gemini_result.get('extracted_answers', [])
                    suggested_marks = gemini_result.get('suggested_marks', [])
                    reasoning = gemini_result.get('reasoning', '')

                    question_results = []
                    total_marks_obtained = 0

                    for idx, q in enumerate(questions):
                        q_marks = q.get('marks', 0)
                        q_num = idx + 1 # Assuming sequential numbering for simplicity if not provided
                        
                        student_ans = ""
                        if idx < len(extracted_answers):
                            student_ans = extracted_answers[idx]
                        
                        marks = 0
                        if idx < len(suggested_marks):
                            try:
                                marks = float(suggested_marks[idx])
                            except (ValueError, TypeError):
                                marks = 0

                        # Ensure marks don't exceed max marks
                        marks = min(marks, q_marks)
                        
                        question_results.append({
                            'question_index': idx,
                            'question_num': q_num,
                            'question_text': q.get('question_text', ''),
                            'extracted_answer': student_ans or f"Answer not found for Question {q_num}.",
                            'ai_marks': marks,
                            'marks_obtained': marks,
                            'total_marks': q_marks,
                            'similarity_score': marks / q_marks if q_marks > 0 else 0
                        })

                        total_marks_obtained += marks

                    avg_similarity = (total_marks_obtained / total_marks) if total_marks > 0 else 0
                    
                    # ------------------------------------------------
                    # STEP 3: CONSTRUCT FEEDBACK
                    # ------------------------------------------------
                    _progress(92, 'Finalizing feedback...')
                    
                    from services.marks_calculator import get_grade
                    grade = get_grade(total_marks_obtained, total_marks)
                    
                    # Keywords: use AI-detected keywords or fallback to extraction
                    ai_keywords = gemini_result.get('matched_keywords', [])
                    if not ai_keywords and raw_text:
                         from services.nlp_preprocessing import extract_keywords
                         ai_keywords = extract_keywords(raw_text)

                    # Build the complex feedback object that the frontend expects
                    feedback = {
                        'grade': grade,
                        'similarity_percentage': round(avg_similarity * 100, 1),
                        'marks_obtained': total_marks_obtained,
                        'total_marks': total_marks,
                        'keyword_analysis': {
                            'matched_keywords': ai_keywords,
                            'missing_keywords': gemini_result.get('weaknesses', [])[:5],
                            'keyword_overlap': len(ai_keywords) * 5, # Simulated percentage or 0
                            'total_model_keywords': len(ai_keywords) + 2
                        },
                        'strengths': gemini_result.get('strengths', ["Good attempt."]),
                        'weaknesses': gemini_result.get('weaknesses', ["Room for more detail."]),
                        'suggestions': gemini_result.get('suggestions', ["Provide more specific examples."]),
                        'reasoning': reasoning
                    }

                   # ------------------------------------------------
                    # BUILD CLEAN STUDENT TEXT
                    # ------------------------------------------------

                    clean_student_text = ""

                    for q in question_results:
                        clean_student_text += f"Question {q['question_num']}: {q['extracted_answer']}\n\n"

                    clean_student_text = clean_student_text.strip()


                    # ------------------------------------------------
                    # STEP 4: SAVE RESULTS
                    # ------------------------------------------------

                    _progress(95, 'Saving final results...')

                    submission_model.update_evaluation(
                        submission_id,
                        clean_student_text,   # <-- CHANGED HERE
                        question_results,
                        avg_similarity,
                        total_marks_obtained,
                        feedback
                    )

                    _progress(100, 'Evaluation complete')

                    elapsed = time.time() - t_start

                    print(f"\n[EVAL] DONE for {submission_id} in {elapsed:.1f}s")
                    print(f"[EVAL] FINAL MARKS: {total_marks_obtained}/{total_marks}\n")

                except Exception as e:

                    import traceback
                    err_msg = traceback.format_exc()
                    _log(f"CRITICAL ERROR: {e}\n{err_msg}")
                    print(f"[EVAL ERROR] Submission {submission_id}: {e}")
                    
                    user_message = str(e).strip() or "Evaluation failed"
                    submission_model.set_progress(submission_id, 100, 'Evaluation failed')
                    submission_model.set_status(submission_id, 'error', error_message=user_message)

                finally:
                    gc.collect()

        finally:
            semaphore.release()
            gc.collect()

    thread = threading.Thread(target=_evaluate, daemon=True)
    thread.start()


@student_bp.route('/assignments', methods=['GET'])
@jwt_required()
def list_assignments():
    user_id, err = _require_student()
    if err:
        return err

    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    assignments = model.get_all(active_only=True)

    # Don't expose model answers to students
    for a in assignments:
        a.pop('model_answer', None)
        for q in a.get('questions', []):
            q.pop('model_answer', None)

    return jsonify({'assignments': assignments}), 200


@student_bp.route('/submit', methods=['POST'])
@jwt_required()
def submit_answer():
    user_id, err = _require_student()
    if err:
        return err

    assignment_id = request.form.get('assignment_id')
    if not assignment_id:
        return jsonify({'error': 'assignment_id is required'}), 400

    # Verify assignment exists
    from models.assignment import AssignmentModel
    assignment_model = AssignmentModel(_get_db())
    assignment = assignment_model.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    # Handle file upload
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use PDF, PNG, JPG, or TXT'}), 400

    # Save file
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Create submission record
    from models.submission import SubmissionModel
    submission_model = SubmissionModel(_get_db())
    submission = submission_model.create(user_id, assignment_id, file_path, ext)
    submission_model.set_status(submission['id'], 'processing', error_message='')
    submission_model.set_progress(submission['id'], 1, 'Queued for evaluation...')

    # Run evaluation pipeline in a background thread so the request returns immediately
    app = current_app._get_current_object()
    _run_evaluation_async(
        app, submission['id'], file_path, ext,
        assignment, assignment['total_marks']
    )

    return jsonify({
        'message': 'Answer submitted successfully. Evaluation is in progress.',
        'submission': submission,
    }), 201


@student_bp.route('/retry/<submission_id>', methods=['POST'])
@jwt_required()
def retry_evaluation(submission_id):
    """Retry evaluation for a stuck/errored submission."""
    user_id, err = _require_student()
    if err:
        return err

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel

    db = _get_db()
    submission_model = SubmissionModel(db)
    assignment_model = AssignmentModel(db)

    submission = submission_model.get_by_id(submission_id)
    if not submission or submission['student_id'] != user_id:
        return jsonify({'error': 'Submission not found'}), 404

    if submission['status'] == 'evaluated':
        return jsonify({'message': 'Already evaluated'}), 200

    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    submission_model.set_status(submission_id, 'processing', error_message='')
    submission_model.set_progress(submission_id, 1, 'Queued for re-evaluation...')

    app = current_app._get_current_object()
    _run_evaluation_async(
        app, submission_id, submission['file_path'],
        submission['file_type'], assignment,
        assignment['total_marks']
    )

    return jsonify({'message': 'Re-evaluation started'}), 200


@student_bp.route('/results', methods=['GET'])
@jwt_required()
def view_results():
    user_id, err = _require_student()
    if err:
        return err

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel

    submission_model = SubmissionModel(_get_db())
    assignment_model = AssignmentModel(_get_db())

    submissions = submission_model.get_by_student(user_id)

    # Enrich with assignment info
    for s in submissions:
        assignment = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment['title'] if assignment else 'Unknown'
        s['assignment_subject'] = assignment['subject'] if assignment else 'Unknown'
        s['total_marks'] = assignment['total_marks'] if assignment else 0

    return jsonify({'results': submissions}), 200
