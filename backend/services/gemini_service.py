import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Using 'gemini-flash-lite-latest' (more likely to have free quota available)
    model = genai.GenerativeModel('gemini-flash-lite-latest')
else:
    logging.warning("GEMINI_API_KEY not found in environment variables.")
    model = None

def evaluate_with_gemini(student_content, questions, file_path=None, file_type=None, marking_scheme=None):
    """
    Evaluates student's answer against a list of questions using Google Gemini.
    Can take either extracted text or a file path (multimodal).
    
    Args:
        student_content (str): Text extracted from student's PDF/Image (if available)
        questions (list): List of { 'question_text': str, 'model_answer': str, 'marks': int }
        file_path (str): Optional path to the PDF/Image file for multimodal extraction
        file_type (str): Optional file extension (pdf, png, jpg, jpeg)
        marking_scheme (str): Optional grading rubric/marking scheme provided by faculty
        
    Returns:
        dict: {
            'extracted_answers': [str, ...],
            'suggested_marks': [float, ...],
            'reasoning': str
        }
    """
    if not model:
        logging.error("Gemini Model not initialized. Check API Key.")
        return None

    # Construct the questions prompt
    questions_formatted = ""
    for idx, q in enumerate(questions):
        questions_formatted += f"Question {idx+1}: {q['question_text']}\n"
        questions_formatted += f"Model Answer {idx+1}: {q['model_answer']}\n"
        questions_formatted += f"Max Marks {idx+1}: {q['marks']}\n\n"

    marking_scheme_formatted = f"\n### Marking Scheme / Rubric:\n{marking_scheme}\n" if marking_scheme else ""

    prompt = f"""
    You are an expert academic evaluator. You are provided with a student's answer script 
    and a list of questions with their model answers.
    {marking_scheme_formatted}
    Your task is to:
    1. Identify and extract the student's answer for each question from the provided content.
    2. Evaluate each extracted answer against the model answer with high precision.
    3. Suggest marks for each answer based on accuracy, completeness, and conceptual clarity (on a scale from 0 to Max Marks).
    4. Provide detailed qualitative feedback:
       - Strengths: What concepts did the student explain well? (Minimum 3 points)
       - Weaknesses: What specific details or key terms are missing? (Minimum 3 points)
       - Suggestions: Actionable tips to improve the specific answer. (Minimum 3 points)
    5. Keywords: Identify the technical key terms that the student successfully used.

    ### Questions & Model Answers:
    {questions_formatted}

    ### Instructions:
    - If it's a file (PDF/Image), perform deep internal OCR to see the student's handwriting.
    - If a student hasn't attempted a question, return an empty string for the extracted answer and 0 for marks.
    - Be fair but strict. Handle minor handwriting/OCR errors gracefully.
    - Focus on technical accuracy and conceptual depth.
    - Return the response STRICTLY as a JSON object in the following format:
    {{
        "extracted_answers": ["answer for Q1", "answer for Q2", ...],
        "suggested_marks": [marks for Q1, marks for Q2, ...],
        "strengths": ["point 1", "point 2", "point 3", ...],
        "weaknesses": ["point 1", "point 2", "point 3", ...],
        "suggestions": ["point 1", "point 2", "point 3", ...],
        "matched_keywords": ["keyword1", "keyword2", ...],
        "reasoning": "Overall comprehensive evaluation summary"
    }}
    """

    try:
        inputs = []
        inputs.append(prompt)
        
        # Add file if provided
        if file_path and os.path.exists(file_path):
            if file_type == 'pdf':
                mime_type = 'application/pdf'
            elif file_type in ['png', 'jpg', 'jpeg']:
                mime_type = f'image/{file_type.replace("jpg", "jpeg")}'
            else:
                mime_type = 'text/plain' # Fallback for txt
                
            with open(file_path, "rb") as f:
                file_data = f.read()
                
            inputs.append({
                "mime_type": mime_type,
                "data": file_data
            })
        elif student_content:
            inputs.append(f"### Student Content (Text extracted via OCR):\n{student_content}")
        else:
            logging.error("Neither text nor file_path provided to Gemini for evaluation.")
            return None

        response = model.generate_content(
            inputs,
            generation_config={"response_mime_type": "application/json"}
        )
        
        if response and response.text:
            result = json.loads(response.text)
            return result
    except Exception as e:
        logging.error(f"Gemini Evaluation Error: {e}")
        import traceback
        traceback.print_exc()
    
    return None
