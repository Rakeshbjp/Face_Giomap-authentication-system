# Face Recognition Authentication System

A production-ready, full-stack face recognition authentication module built with **React.js**, **FastAPI**, **MongoDB**, and **DeepFace (Facenet512)**.

---

## Features

- **Dual Authentication** — Email/password + mandatory face verification
- **Multi-Angle Face Capture** — 4-direction registration (front, left, right, up/down)
- **Liveness Detection** — Anti-spoofing checks (positional variance + identity consistency)
- **Encrypted Embeddings** — Face data stored as AES-encrypted vectors, never raw images
- **Real-Time Verification** — Sub-2-second face matching using cosine similarity
- **JWT Auth** — Access + refresh tokens with secure expiration
- **Rate Limiting** — Per-IP request throttling
- **Security Headers** — HSTS, X-Frame-Options, CSP
- **Responsive** — Works on mobile, tablet, and desktop browsers

---

## Tech Stack

| Layer | Technology |
| ------- | ----------- |
| Frontend | React 18, React Router, Tailwind CSS, Vite |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | MongoDB 7 (Motor async driver) |
| Face AI | DeepFace (Facenet512 model) |
| Security | bcrypt, PyJWT, Fernet encryption |
| DevOps | Nginx (optional), Uvicorn |

---

## Project Structure

```text
face-auth/
├── backend/
│   ├── app/
│   │   ├── config/
│   │   │   ├── settings.py          # Environment config (Pydantic)
│   │   │   └── database.py          # MongoDB connection (Motor)
│   │   ├── models/
│   │   │   └── user.py              # Pydantic schemas (request/response/DB)
│   │   ├── services/
│   │   │   ├── auth_service.py      # Registration, login, JWT, face verify
│   │   │   └── face_recognition.py  # Embedding extraction, comparison, liveness
│   │   ├── routes/
│   │   │   └── auth_routes.py       # API endpoints
│   │   ├── middleware/
│   │   │   └── auth_middleware.py    # JWT guard, rate limiter, security headers
│   │   └── utils/
│   │       ├── encryption.py        # Fernet embedding encryption/decryption
│   │       └── logging_config.py    # Structured logging setup
│   ├── main.py                      # FastAPI app entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── face/
│   │   │   │   ├── FaceCaptureRegistration.jsx  # 4-direction face capture
│   │   │   │   └── FaceVerification.jsx         # Real-time face verify
│   │   │   └── ui/
│   │   │       ├── Navbar.jsx
│   │   │       ├── Spinner.jsx
│   │   │       └── StatusBadge.jsx
│   │   ├── context/
│   │   │   └── AuthContext.jsx      # Global auth state
│   │   ├── hooks/
│   │   │   └── useCamera.js         # Webcam access hook
│   │   ├── pages/
│   │   │   ├── HomePage.jsx
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   └── DashboardPage.jsx
│   │   ├── services/
│   │   │   ├── api.js               # Axios instance
│   │   │   └── authService.js       # API call wrappers
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── nginx.conf
└── README.md
```

---

## MongoDB User Schema

```json
{
  "_id": "ObjectId",
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "password_hash": "$2b$12$...",
  "face_embeddings": [
    "gAAAAABl...encrypted_vector_1...",
    "gAAAAABl...encrypted_vector_2...",
    "gAAAAABl...encrypted_vector_3...",
    "gAAAAABl...encrypted_vector_4..."
  ],
  "liveness_verified": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

---

## API Endpoints

| Method | Endpoint | Description | Auth |
| -------- | ---------- | ------------- | ------ |
| POST | `/api/auth/register` | Register with face images | Public |
| POST | `/api/auth/login` | Login with email + password | Public |
| POST | `/api/auth/verify-face` | Verify face after login | Public |
| POST | `/api/auth/face-login` | Login using face only | Public |
| GET | `/api/auth/profile` | Get user profile | JWT |
| GET | `/api/auth/health` | Health check | Public |

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **MongoDB** (local or Atlas)
- **Webcam** (for face capture)

### 1. Clone & Setup

```bash
git clone <repository-url>
cd face-auth
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings (especially JWT_SECRET_KEY and EMBEDDING_ENCRYPTION_KEY)

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs` (only in DEBUG mode).

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The app will be available at `http://localhost:3000`.

### 4. Start MongoDB

```bash
# Start local MongoDB service (if installed as a service)
mongod

# Or use MongoDB Atlas: https://www.mongodb.com/atlas
```

---

## Deployment Guide

### Railway / Render

1. **Backend**: Deploy the `backend/` directory as a Python service
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Set all environment variables from `.env.example`

2. **Frontend**: Deploy the `frontend/` directory as a static site
   - Build command: `npm install && npm run build`
   - Publish directory: `dist`
   - Set `VITE_API_URL` to your backend URL

3. **MongoDB**: Use [MongoDB Atlas](https://www.mongodb.com/atlas) free tier
   - Update `MONGODB_URL` with your Atlas connection string

### Vercel (Frontend Only)

```bash
cd frontend
npx vercel --prod
```

Set `VITE_API_URL` environment variable in Vercel dashboard.

---

## Security Best Practices

| Practice | Implementation |
| ---------- | --------------- |
| Password hashing | bcrypt with 12 salt rounds |
| Token auth | JWT with short-lived access tokens (30 min) |
| Face data | Encrypted with AES-128 (Fernet), never stored as images |
| Anti-spoofing | Multi-angle liveness detection with positional variance check |
| Rate limiting | Per-IP request throttling (100 req/min default) |
| Security headers | HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff |
| CORS | Strict origin allow-list |
| Input validation | Pydantic models on every endpoint |
| HTTPS | Enforced via proxy in production |
| Replay prevention | Short JWT expiry + per-request token validation |

---

## Environment Variables

### Backend

| Variable | Description | Default |
| ---------- | ------------- | --------- |
| `MONGODB_URL` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | Database name | `face_auth_db` |
| `JWT_SECRET_KEY` | JWT signing secret | **Must change!** |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `30` |
| `FACE_SIMILARITY_THRESHOLD` | Match threshold (0-1) | `0.75` |
| `FACE_MODEL` | DeepFace model | `Facenet512` |
| `EMBEDDING_ENCRYPTION_KEY` | AES encryption key | **Must change!** |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `100` |
| `CORS_ORIGINS` | Allowed origins (comma-sep) | `http://localhost:3000` |
| `DEBUG` | Enable debug mode | `False` |

### Frontend

| Variable       | Description          | Default |
| -------------- | -------------------- | ------- |
| `VITE_API_URL` | Backend API base URL | `/api`  |

---

## Authentication Flow

```text
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│   Register   │          │    Login     │          │  Dashboard   │
│              │          │              │          │              │
│ 1. Fill form │          │ 1. Email+Pwd │          │  ✅ Fully    │
│ 2. Capture   │────→     │ 2. Face      │────→     │  Authenticated│
│    4 faces   │          │    Verify    │          │              │
│ 3. Liveness  │          │ 3. JWT issued│          │              │
│    check     │          │              │          │              │
└──────────────┘          └──────────────┘          └──────────────┘
```

---

## License

MIT
