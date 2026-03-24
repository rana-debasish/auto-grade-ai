"""Evaluation Manager — Orchestrates the background evaluation process."""

import gc
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from flask import current_app

def run_evaluation_async(app, submission_id, file_path, file_type, assignment, total_marks):
    """
    Triggers the background evaluation process.
    """
    def _evaluate():
        from app import db, evaluation_semaphore
        from models.submission import SubmissionModel
        from services.image_processing import preprocess_image
        from services.ocr_service import extract_text, extract_text_from_file
        from services.gemini_service import evaluate_with_gemini
        from services.marks_calculator import get_grade
        from config import Config
        import re

        def clean_ocr_text(text):
            if not text: return ""
            text = re.sub(r'\[.*?ppocr.*?\]', ' ', text)
            text = re.sub(r'Namespace\(.*?\)', ' ', text)
            text = re.sub(r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', ' ', text)
            text = re.sub(r'[^a-zA-Z0-9\s.,;:!?\'\"/()\[\]{}@#$%&*+=<>_-]', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        semaphore = evaluation_semaphore
        if not semaphore.acquire(blocking=True, timeout=300):
            print(f"[EVAL] Timeout waiting for semaphore: {submission_id}")
            return

        try:
            with app.app_context():
                submission_model = SubmissionModel(db)
                
                def _progress(pct, step):
                    submission_model.set_progress(submission_id, pct, step)

                try:
                    t_start = time.time()
                    _progress(5, 'Extracting text from document...')
                    
                    raw_text = extract_text_from_file(file_path) or ""
                    raw_text = clean_ocr_text(raw_text)

                    if not raw_text and file_type in ["png", "jpg", "jpeg"]:
                        _progress(10, 'Preprocessing image for OCR...')
                        processed_image = preprocess_image(file_path)
                        _progress(30, 'Performing OCR extraction...')
                        raw_text = extract_text(processed_image) or ""
                        raw_text = clean_ocr_text(raw_text)
                        del processed_image
                        gc.collect()

                    if raw_text:
                        raw_text = raw_text[:Config.MAX_EXTRACTED_CHARS]
                    
                    _progress(60, 'Text extracted')
                    _progress(70, 'AI Analysis in progress...')

                    questions = assignment.get('questions', [])[:25]
                    marking_scheme = assignment.get('marking_scheme')
                    
                    gemini_result = evaluate_with_gemini(
                        raw_text, 
                        questions, 
                        file_path=file_path, 
                        file_type=file_type,
                        marking_scheme=marking_scheme
                    )
                    
                    if not gemini_result:
                        raise ValueError("AI Evaluation failed. Please try again.")

                    extracted_answers = gemini_result.get('extracted_answers', [])
                    suggested_marks = gemini_result.get('suggested_marks', [])
                    reasoning = gemini_result.get('reasoning', '')

                    question_results = []
                    total_marks_obtained = 0

                    for idx, q in enumerate(questions):
                        q_marks = q.get('marks', 0)
                        q_num = idx + 1
                        
                        student_ans = ""
                        if idx < len(extracted_answers):
                            student_ans = extracted_answers[idx]
                        
                        marks = 0
                        if idx < len(suggested_marks):
                            try:
                                marks = float(suggested_marks[idx])
                            except:
                                marks = 0

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
                    
                    _progress(92, 'Finalizing feedback...')
                    grade = get_grade(total_marks_obtained, total_marks)
                    
                    ai_keywords = gemini_result.get('matched_keywords', [])
                    
                    feedback = {
                        'grade': grade,
                        'similarity_percentage': round(avg_similarity * 100, 1),
                        'marks_obtained': total_marks_obtained,
                        'total_marks': total_marks,
                        'keyword_analysis': {
                            'matched_keywords': ai_keywords,
                            'missing_keywords': gemini_result.get('weaknesses', [])[:5],
                            'keyword_overlap': len(ai_keywords) * 5,
                            'total_model_keywords': len(ai_keywords) + 2
                        },
                        'strengths': gemini_result.get('strengths', ["Good attempt."]),
                        'weaknesses': gemini_result.get('weaknesses', ["Room for more detail."]),
                        'suggestions': gemini_result.get('suggestions', ["Provide more specific examples."]),
                        'reasoning': reasoning
                    }

                    clean_student_text = ""
                    for q in question_results:
                        clean_student_text += f"Question {q['question_num']}: {q['extracted_answer']}\n\n"

                    _progress(95, 'Saving final results...')
                    submission_model.update_evaluation(
                        submission_id,
                        clean_student_text.strip(),
                        question_results,
                        avg_similarity,
                        total_marks_obtained,
                        feedback
                    )
                    _progress(100, 'Evaluation complete')

                except Exception as e:
                    print(f"[EVAL ERROR] Submission {submission_id}: {e}")
                    traceback.print_exc()
                    submission_model.set_status(submission_id, 'error', error_message=str(e))

                finally:
                    gc.collect()
        finally:
            semaphore.release()

    thread = threading.Thread(target=_evaluate, daemon=True)
    thread.start()
