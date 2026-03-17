"""NLP Preprocessing Module — Optimized for high-precision Question/Answer differentiation."""

import re
import os
import nltk

# Set NLTK data path
NLTK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'nltk_data')
os.makedirs(NLTK_DATA_DIR, exist_ok=True)
if NLTK_DATA_DIR not in nltk.data.path:
    nltk.data.path.insert(0, NLTK_DATA_DIR)

# Global variables for NLTK resources
_stop_words = set()
_lemmatizer = None

def init_nltk():
    global _stop_words, _lemmatizer
    for res in [('tokenizers/punkt', 'punkt'), ('tokenizers/punkt_tab', 'punkt_tab'), ('corpora/stopwords', 'stopwords'), ('corpora/wordnet', 'wordnet')]:
        try:
            nltk.data.find(res[0])
        except Exception:
            try:
                nltk.download(res[1], quiet=True, download_dir=NLTK_DATA_DIR)
            except Exception as e:
                print(f"[NLP] Warning: Could not download {res[1]}: {e}")

    try:
        from nltk.corpus import stopwords
        _stop_words = set(stopwords.words('english'))
    except Exception:
        _stop_words = {'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now'}

    try:
        from nltk.stem import WordNetLemmatizer
        _lemmatizer = WordNetLemmatizer()
    except Exception:
        _lemmatizer = None

# Initialize on import
init_nltk()

def preprocess_text(text):
    if not text or not str(text).strip(): return ''
    text = str(text)
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    tokens = [t for t in text.split() if t not in _stop_words and len(t) > 1]
    if _lemmatizer:
        try:
            tokens = [_lemmatizer.lemmatize(t) for t in tokens]
        except Exception: pass
    return ' '.join(tokens)

def parse_model_answers(text, default_total_marks=100):
    """
    High-precision parser: Identifies Question Number, Question Text, and Model Answer.
    """
    if not text or not text.strip(): return []

    # Find all question markers (1., 2., Q1, etc)
    pattern = r'(?:^|\n)\s*(?:Q|Question|#)?\s*(\d+)[.:\)]?\s*'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    
    if not matches:
        return [{
            'question_text': 'Question 1',
            'question_text_original': 'Main Question',
            'model_answer': text.strip(),
            'marks': default_total_marks,
            'original_num': '1'
        }]

    results = []
    for i in range(len(matches)):
        q_num = matches[i].group(1)
        start = matches[i].end()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        
        block = text[start:end].strip()
        
        # 1. Extract Marks [10] or (10 marks)
        marks = 10
        marks_match = re.search(r'(?:\[|\()(?:\s*marks?:\s*)?\s*(\d+)\s*(?:marks?|pts)?(?:\s*\]|\))', block, re.IGNORECASE)
        if marks_match:
            try:
                marks = int(marks_match.group(1))
                block = block.replace(marks_match.group(0), '').strip()
            except Exception: pass

        # 2. Differentiate Question from Answer
        q_original = ""
        ans_original = block
        
        q_end_match = re.search(r'\?|\n\n', block)
        if q_end_match:
            split_point = q_end_match.end()
            q_original = block[:split_point].strip()
            ans_original = block[split_point:].strip()
        else:
            lines = block.split('\n', 1)
            q_original = lines[0].strip()
            ans_original = lines[1].strip() if len(lines) > 1 else block

        results.append({
            'question_text': f'Question {q_num}',
            'question_text_original': q_original,
            'model_answer': ans_original,
            'marks': marks,
            'original_num': q_num
        })
    return results

def segment_student_answers(raw_text, questions):
    """
    Surgical Segmenter: Uses the blueprint of model questions to extract 
    and clean student answers from a raw bulk text.
    """
    if not raw_text: return {}
    
    # Fix common OCR errors
    ocr_corrections = {
        "Cuestion": "Question",
        "Queston": "Question",
        "Queshon": "Question",
        "Bingry": "Binary",
        "lebt": "left",
        "lront": "front",
        "Lrro": "LIFO"
    }
    for error, fix in ocr_corrections.items():
        raw_text = raw_text.replace(error, fix)
    
    pattern = r'(?:Q|Question|#)?\s*[-:]?\s*(\d+)'
    markers = list(re.finditer(pattern, raw_text, re.IGNORECASE))
    
    segments = {}
    
    # Process each found marker
    for i in range(len(markers)):
        try:
            q_num_found = markers[i].group(1)
            start = markers[i].end()
            end = markers[i+1].start() if i+1 < len(markers) else len(raw_text)
            
            content = raw_text[start:end].strip()
            
            # Find the reference question from the teacher's model
            ref_q = next((q for q in questions if str(q.get('original_num')) == str(q_num_found)), None)
            
            if ref_q:
                ref_text = ref_q.get('question_text_original', '').strip()
                if ref_text:
                    content = _strip_question_prefix(content, ref_text)
            
            segments[str(q_num_found)] = content.strip()
        except Exception as e:
            print(f"[NLP] Error segmenting question: {e}")

    return segments


def extract_keywords(text, max_keywords=20):
    """
    Extract important keywords from text after preprocessing.
    """
    cleaned = preprocess_text(text)

    words = cleaned.split()

    # Remove duplicates but keep order
    seen = set()
    keywords = []

    for w in words:
        if w not in seen:
            keywords.append(w)
            seen.add(w)

    return keywords[:max_keywords]

def _strip_question_prefix(student_block, teacher_question):
    """
    Removes the teacher's question text from the start of the student's block.
    """
    if not student_block or not teacher_question: return student_block
    
    try:
        def clean(t): return re.sub(r'[^a-z0-9]', '', str(t).lower())
        
        s_clean = clean(student_block)
        t_clean = clean(teacher_question)
        
        if s_clean.startswith(t_clean):
            char_count = 0
            cleaned_so_far = ""
            for char in student_block:
                char_count += 1
                if re.match(r'[a-z0-9]', char, re.I):
                    cleaned_so_far += char.lower()
                if cleaned_so_far == t_clean:
                    return student_block[char_count:].strip().lstrip('.:- \n')
                    
        lines = student_block.split('\n', 1)
        if len(lines) > 1 and len(clean(lines[0])) > 10:
            if clean(lines[0]) in t_clean or t_clean in clean(lines[0]):
                return lines[1].strip()
    except Exception: pass

    return student_block
