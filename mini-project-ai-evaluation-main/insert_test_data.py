import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

print("========== MongoDB Insert Test ==========")

# Load .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME")

try:
    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    client.admin.command("ping")

    print("✅ Connected to MongoDB Atlas")

    db = client[DB_NAME]
    submissions = db["submissions"]

    # Test document
    data = {
        "student_id": "test_student",
        "assignment_id": "test_assignment",
        "extracted_text": "This is a test OCR extracted text.",
        "question_results": [
            {
                "question_index": 0,
                "extracted_answer": "Machine learning is a subset of AI.",
                "similarity_score": 0.88,
                "ai_marks": 9,
                "marks_obtained": 9
            }
        ],
        "similarity_score": 0.88,
        "marks_obtained": 9,
        "status": "evaluated",
        "submitted_at": datetime.now(timezone.utc)
    }

    # Insert into database
    result = submissions.insert_one(data)

    print("✅ Data inserted successfully!")
    print("Inserted ID:", result.inserted_id)

except Exception as e:
    print("❌ Error inserting data:")
    print(e)