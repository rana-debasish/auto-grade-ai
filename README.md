# 🎓 AI-Based Answer Script Evaluation System

An intelligent system that evaluates student answer scripts using AI — combining OCR, NLP, and LLM techniques to automatically grade and provide feedback.

## ✨ Features

- **Multi-format Upload** — Supports PDF, PNG, JPG, JPEG, TXT, DOCX files
- **AI-Powered Evaluation** — Google Gemini API for extraction and grading
- **OCR Text Extraction** — PyMuPDF for digital documents
- **Split-View Grading** — Review PDF and assign marks side-by-side
- **Detailed Feedback** — Per-question marks, justification, and correctness
- **Role-Based Access** — Students, Faculty, and Admin dashboards
- **Reports & Export** — Faculty can download Excel reports
- **Theme Support** — Light, Dark, and System theme modes
- **Memory Optimized** — Designed for deployment on Render free tier (512MB RAM)

## 🏗️ Architecture

```
┌──────────────────────────────────────────────┐
│                  Frontend                     │
│   HTML + CSS + JavaScript (SPA)               │
│   Login │ Student │ Faculty │ Admin            │
└──────────────────┬───────────────────────────┘
                   │ REST API (JWT Auth)
┌──────────────────┴───────────────────────────┐
│              Flask Backend                    │
│   Routes → Services → Models                 │
│                                              │
│   ┌────────────┐  ┌──────────────────────┐   │
│   │ OCR        │  │ Evaluation Engine    │   │
│   │ PyMuPDF    │  │ Google Gemini API    │   │
│   └────────────┘  └──────────────────────┘   │
└──────────────────┬───────────────────────────┘
                   │
          ┌────────┴────────┐
          │   MongoDB Atlas  │
          └─────────────────┘
```

## 📁 Project Structure

```
├── backend/
│   ├── app.py                 # Flask application & configuration
│   ├── config.py              # Environment-based configuration
│   ├── seed.py                # Admin user seeding script
│   ├── models/
│   │   ├── user.py            # User model (students, faculty, admin)
│   │   ├── assignment.py      # Assignment model (questions + model answers)
│   │   └── submission.py      # Submission model (student submissions + results)
│   ├── routes/
│   │   ├── auth.py            # Authentication (login, register)
│   │   ├── student.py         # Student endpoints (submit, view results)
│   │   ├── faculty.py         # Faculty endpoints (create assignments, reviews)
│   │   └── admin.py           # Admin endpoints (manage users, stats)
│   ├── services/
│   │   ├── gemini_service.py      # Google Gemini API integration
│   │   ├── nlp_preprocessing.py   # Text cleaning and parsing
│   │   └── ocr_service.py         # Text extraction from documents
│   ├── uploads/               # Temporary file storage
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── index.html             # Login/Register page
│   ├── student.html           # Student dashboard
│   ├── faculty/               # Faculty dashboard & tools
│   │   ├── dashboard.html     # Assignment list
│   │   ├── edit_evaluation.html # Split-view grading tool
│   │   └── reports.html       # Analytics
│   ├── admin.html             # Admin dashboard
│   ├── css/                   # Stylesheets
│   └── js/
│       ├── auth.js            # Authentication logic
│       ├── student.js         # Student interface
│       ├── faculty.js         # Faculty interface
│       └── admin.js           # Admin interface
├── start_with_ngrok.py        # Launcher with ngrok tunnel
├── .env.example               # Environment template
├── Run_on_Colab.ipynb         # Google Colab notebook
└── README.md                  # This file
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **MongoDB** (local or [MongoDB Atlas](https://www.mongodb.com/atlas) free tier)
- **Git** (optional)

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ai-answer-evaluation.git
   cd ai-answer-evaluation
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Download NLTK data**
   ```bash
   python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords'); nltk.download('wordnet')"
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your MongoDB URI and JWT secret
   ```

6. **Seed the admin user**
   ```bash
   cd backend
   python seed.py
   ```

7. **Run the application**
   ```bash
   python app.py
   ```
   Visit: [http://localhost:5000](http://localhost:5000)

### Default Admin Credentials

| Field    | Value              |
|----------|--------------------|
| Email    | admin@system.com   |
| Password | admin123           |

> ⚠️ **Change the admin password immediately after first login.**

## ☁️ Google Colab

Open `Run_on_Colab.ipynb` in Google Colab and follow the step-by-step cells:

1. Upload/clone the project
2. Install dependencies
3. Enter your MongoDB URI and ngrok token
4. Seed admin user
5. Start the server — get a public URL!

**Requirements for Colab:**
- [MongoDB Atlas](https://www.mongodb.com/atlas) free tier connection string
- [ngrok](https://ngrok.com) free auth token

## 🌐 Render Deployment

The project includes `Procfile`, `render.yaml`, and `runtime.txt` for one-click Render deployment.

1. Push to GitHub
2. Connect your repo to [Render](https://render.com)
3. Set environment variables:
   - `MONGO_URI` — your MongoDB Atlas connection string
   - `JWT_SECRET_KEY` — auto-generated by Render
4. Deploy!

**Memory Optimization:** The app is pre-configured for Render's free tier (512MB RAM):
- Single concurrent evaluation
- Memory-efficient PDF processing
- Automatic garbage collection
- Health monitoring at `/api/health`

## 🔧 Configuration

All settings are configured via environment variables (see `.env.example`):

| Variable                     | Default                          | Description                     |
|------------------------------|----------------------------------|---------------------------------|
| `MONGO_URI`                  | `mongodb://localhost:27017/`     | MongoDB connection string       |
| `MONGO_DB_NAME`              | `answer_evaluation_system`       | Database name                   |
| `JWT_SECRET_KEY`             | (dev key)                        | JWT signing secret              |
| `JWT_ACCESS_TOKEN_EXPIRES`   | `86400`                          | Token TTL in seconds (24h)      |
| `FLASK_DEBUG`                | `0`                              | Enable debug mode (1/0)         |
| `MAX_CONTENT_LENGTH`         | `8388608`                        | Max upload size (8MB)           |
| `MAX_CONCURRENT_EVALUATIONS` | `1`                              | Parallel evaluation limit       |
| `MAX_PDF_PAGES`              | `10`                             | Max pages to process per PDF    |

## 🛡️ Security Notes

- Never commit `.env` with real credentials (it's in `.gitignore`)
- Change the default admin password after seeding
- Use a strong, random `JWT_SECRET_KEY` in production
- MongoDB credentials should use dedicated app users, not admin accounts

## 📋 API Endpoints

### Authentication
| Method | Endpoint           | Description     |
|--------|-------------------|-----------------|
| POST   | `/api/auth/login`  | User login      |
| POST   | `/api/auth/register` | User registration |

### Student
| Method | Endpoint                          | Description            |
|--------|----------------------------------|------------------------|
| GET    | `/api/student/assignments`        | List available assignments |
| POST   | `/api/student/submit/<id>`        | Submit answer script   |
| GET    | `/api/student/results`            | View all results       |
| GET    | `/api/student/result/<id>`        | View specific result   |

### Teacher
| Method | Endpoint                          | Description              |
|--------|----------------------------------|--------------------------|
| POST   | `/api/teacher/assignment`         | Create assignment        |
| GET    | `/api/teacher/submissions/<id>`   | View submissions         |
| PUT    | `/api/teacher/submission/<id>/marks` | Edit marks            |
| GET    | `/api/teacher/reports`            | Generate reports         |

### Admin
| Method | Endpoint                    | Description          |
|--------|-----------------------------|----------------------|
| GET    | `/api/admin/stats`          | System statistics    |
| GET    | `/api/admin/users`          | List all users       |
| PUT    | `/api/admin/user/<id>`      | Update user          |
| DELETE | `/api/admin/user/<id>`      | Delete user          |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is for educational purposes.
