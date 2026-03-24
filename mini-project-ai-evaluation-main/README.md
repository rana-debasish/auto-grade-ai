# 🎓 AI-Based Answer Script Evaluation System

An intelligent system that evaluates student answer scripts using AI — combining OCR, NLP, and LLM techniques to automatically grade and provide feedback.

## ✨ Features

- **Multi-student Bulk Evaluation** — Upload multiple answer scripts at once for automated "Evaluate All" grading.
- **Smart Name Extraction** — Automatically detects student names from filenames (e.g., `23rahul.pdf` → `Student: 23rahul`).
- **AI-Powered Evaluation** — Google Gemini API integration for deep answer analysis and scoring.
- **Custom Marking Schemes** — Optional rubrics to guide the AI on strictness and specific grading criteria.
- **OCR & Multimodal Processing** — Advanced extraction using PyMuPDF and Google's latest multimodal models.
- **Split-View Grading** — Faculty can review AI grades alongside original student PDFs.
- **Private Submissions** — Teacher-led evaluations are kept private and hidden from standard student dashboards.
- **Role-Based Access** — Secure dashboards for Students, Faculty, and Admin.
- **Analytics & Export** — Detailed performance reports with Excel export functionality.

```
┌──────────────────────────────────────────────┐
│                  Frontend                     │
│   Vanilla JS + Bootstrap 5 + Glassmorphism    │
│   Login │ Student │ Faculty │ Admin            │
└──────────────────┬───────────────────────────┘
                   │ REST API (JWT Auth)
┌──────────────────┴───────────────────────────┐
│              Flask Backend                    │
│   Routes → Services → Models                 │
│                                              │
│   ┌────────────────────┐  ┌──────────────┐   │
│   │ Evaluation Manager │  │ OCR Service  │   │
│   │ (Background Tasks) │  │ (PyMuPDF)    │   │
│   └──────────┬─────────┘  └──────────────┘   │
│              │
│   ┌──────────┴─────────┐
│   │ Google Gemini API  │
│   │ (Vision & Text)    │
│   └────────────────────┘
└──────────────────┬───────────────────────────┘
                   │
          ┌────────┴────────┐
          │   MongoDB Atlas  │
          └─────────────────┘
```

```
├── backend/
│   ├── app.py                 # Flask application entry point
│   ├── models/
│   │   ├── user.py            # RBAC User definitions
│   │   ├── assignment.py      # Assignment & Marking Scheme storage
│   │   └── submission.py      # Student scripts & AI results
│   ├── routes/
│   │   ├── auth.py            # JWT-based security
│   │   ├── student.py         # Student submission flow
│   │   ├── faculty.py         # Assignment creation & Bulk eval
│   │   └── admin.py           # System management
│   ├── services/
│   │   ├── evaluation_manager.py # Shared evaluation pipeline (Async)
│   │   ├── gemini_service.py     # AI Model integration
│   │   └── ocr_service.py        # Text & Image processing
│   └── uploads/               # Secure script storage
├── frontend/
│   ├── faculty/               # Faculty tools (Dashboard, Eval, Reports)
│   ├── student.html           # Student results & profile
│   └── js/                    # Modular JS controllers
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
| Method | Endpoint                    | Description                  |
|--------|-----------------------------|------------------------------|
| GET    | `/api/student/assignments`  | List active assignments      |
| POST   | `/api/student/submit/<id>`  | Upload answer script         |
| GET    | `/api/student/results`      | View evaluated results       |
| GET    | `/api/student/result/<id>`  | View specific evaluation detail|
| POST   | `/api/student/retry/<id>`   | Re-trigger AI evaluation      |

### Faculty
| Method | Endpoint                         | Description                    |
|--------|----------------------------------|--------------------------------|
| POST   | `/api/faculty/assignment`        | Create Assignment + Bulk Eval  |
| GET    | `/api/faculty/assignments`       | List managed assignments       |
| GET    | `/api/faculty/submissions`       | Filtered student scripts       |
| GET    | `/api/faculty/evaluation/<id>`   | Fetch detailed AI analysis     |
| POST   | `/api/faculty/evaluation/update` | Manual mark override & feedback|
| GET    | `/api/faculty/reports`           | Assignment performance stats   |

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
