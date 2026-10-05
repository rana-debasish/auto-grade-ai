"""Gemini evaluation with bounded retries, fallback, and rubric validation."""

import json
import logging
import os
import random
import re
import time

import google.generativeai as genai
from dotenv import load_dotenv

from config import Config

load_dotenv()
logger = logging.getLogger(__name__)
API_KEY = os.getenv('GEMINI_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

QUESTION_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'q_no': {'type': 'INTEGER'}, 'marks': {'type': 'NUMBER'},
        'extracted_answer': {'type': 'STRING'}, 'feedback': {'type': 'STRING'},
        'confidence': {'type': 'NUMBER'},
        'matched_points': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'missing_points': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
    },
    'required': ['q_no', 'marks', 'extracted_answer', 'feedback', 'confidence', 'matched_points', 'missing_points'],
}
RESPONSE_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'questions': {'type': 'ARRAY', 'items': QUESTION_SCHEMA},
        'overall_feedback': {'type': 'OBJECT', 'properties': {
            'summary': {'type': 'STRING'}, 'strengths': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
            'weaknesses': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
            'suggestions': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        }},
    },
    'required': ['questions', 'overall_feedback'],
}


def _transient(error):
    name = type(error).__name__.lower()
    message = str(error).lower()
    code = getattr(error, 'code', None)
    code_text = str(code).lower() if code is not None else ''
    return any(token in name + ' ' + message + ' ' + code_text for token in
               ('429', 'resourceexhausted', 'ratelimit', '503', '502', '500', 'unavailable', 'deadlineexceeded', 'timeout', 'internalservererror'))


def call_gemini(prompt, files=None, *, model_name=None, stricter=False):
    """Call one configured model, retrying transient failures at most three times."""
    if not API_KEY:
        raise RuntimeError('Gemini is not configured. Set GEMINI_API_KEY and retry.')
    selected = model_name or Config.GEMINI_MODEL
    model = genai.GenerativeModel(selected)
    parts = [prompt]
    if files:
        parts.extend(files)
    if stricter:
        parts.append('Validation reminder: return every question exactly once, valid JSON only, and marks within the provided range.')
    started = time.perf_counter()
    last_error = None
    for attempt in range(4):
        try:
            response = model.generate_content(
                parts,
                generation_config={
                    'temperature': 0.15,
                    'response_mime_type': 'application/json',
                    'response_schema': RESPONSE_SCHEMA,
                },
                request_options={'timeout': Config.GEMINI_TIMEOUT_SECONDS},
            )
            if not response or not response.text:
                raise ValueError('Gemini returned an empty response.')
            parsed = json.loads(response.text)
            usage = getattr(response, 'usage_metadata', None)
            token_count = getattr(usage, 'total_token_count', None) if usage else None
            logger.info('Gemini response model=%s latency_ms=%d total_tokens=%s', selected,
                        int((time.perf_counter() - started) * 1000), token_count if token_count is not None else 'unavailable')
            return parsed
        except Exception as error:
            last_error = error
            if isinstance(error, ValueError) and 'empty response' in str(error).lower():
                raise
            if attempt >= 3 or not _transient(error):
                break
            delay = min(8.0, 0.6 * (2 ** attempt)) + random.uniform(0.05, 0.45)
            logger.warning('Gemini transient failure model=%s attempt=%d retry_in=%.2fs', selected, attempt + 1, delay)
            time.sleep(delay)
    raise RuntimeError(f'Gemini model {selected} failed after retries: {last_error}') from last_error


def _prompt_for(questions, marking_scheme):
    rubric = []
    for index, question in enumerate(questions):
        rubric.append({
            'q_no': question.get('q_no', index + 1),
            'question': question.get('question') or question.get('question_text', ''),
            'max_marks': question.get('max_marks', question.get('marks', 0)),
            'model_answer': question.get('model_answer', ''),
            'key_points': question.get('keywords', []),
        })
    extra = f'Faculty marking scheme: {marking_scheme}' if isinstance(marking_scheme, str) and marking_scheme else ''
    return f"""Evaluate a student's answer script using the rubric below.
{extra}
For every rubric row, return one question object with q_no, marks, extracted_answer,
feedback, confidence (0 to 1), matched_points, and missing_points. Marks must be
numeric and between 0 and that question's max_marks. Use the key points as rubric
criteria, distinguish missing from incorrect concepts, and do not infer identity.
Return overall_feedback with summary, strengths, weaknesses, and suggestions.
Rubric JSON: {json.dumps(rubric, ensure_ascii=False)}"""


def _valid_result(result, questions):
    if not isinstance(result, dict) or not isinstance(result.get('questions'), list): return False
    submitted = result['questions']
    expected = {str(question.get('q_no', index + 1)): question for index, question in enumerate(questions)}
    found = {}
    for row in submitted:
        if not isinstance(row, dict): return False
        key = str(row.get('q_no', ''))
        if key in found or key not in expected: return False
        try: marks, confidence = float(row['marks']), float(row['confidence'])
        except (KeyError, TypeError, ValueError): return False
        maximum = float(expected[key].get('max_marks', expected[key].get('marks', 0)) or 0)
        if not 0 <= marks <= maximum or not 0 <= confidence <= 1: return False
        if not isinstance(row.get('feedback'), str) or not isinstance(row.get('extracted_answer'), str): return False
        found[key] = True
    return len(found) == len(expected)


def _input_parts(student_content, file_path, file_type):
    if student_content:
        return [f'Student answer text (identifiers removed where recognized):\n{student_content}']
    if not file_path or not os.path.isfile(file_path):
        raise ValueError('No readable answer content was provided for evaluation.')
    mime_type = {'pdf': 'application/pdf', 'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}.get(file_type, 'application/octet-stream')
    with open(file_path, 'rb') as source:
        return [{'mime_type': mime_type, 'data': source.read()}]


def evaluate_with_gemini(student_content, questions, file_path=None, file_type=None, marking_scheme=None):
    if not API_KEY:
        raise RuntimeError('Gemini is not configured. Set GEMINI_API_KEY and retry.')
    prompt = _prompt_for(questions, marking_scheme)
    files = _input_parts(student_content, file_path, file_type)
    failures = []
    for model_name in (Config.GEMINI_MODEL, Config.GEMINI_FALLBACK_MODEL):
        if not model_name or model_name in failures: continue
        try:
            result = call_gemini(prompt, files, model_name=model_name)
            if not _valid_result(result, questions):
                result = call_gemini(prompt, files, model_name=model_name, stricter=True)
            if _valid_result(result, questions): return result
            raise ValueError('Gemini returned missing questions, invalid confidence, or marks outside the rubric.')
        except Exception as error:
            failures.append(model_name)
            logger.warning('Gemini model did not produce a valid rubric result model=%s error=%s', model_name, error)
    raise RuntimeError('The AI service could not return a complete valid evaluation. Please retry later.')
