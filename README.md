# AgriRoots

AgriRoots is an AI-assisted farming advisory app for Ethiopian farmers. It supports chat-based agricultural guidance, crop disease diagnosis, weather/soil-aware recommendations, farm risk alerts, OTP authentication, English voice, Amharic voice, a custom sorghum disease model, and a custom enset disease model.

- Frontend URL example: https://agriroots.example.com/
- Backend API URL example: https://api.agriroots.example.com/
- Frontend hosting: Vercel
- Backend hosting: DigitalOcean Ubuntu

## Features

- Phone-number OTP registration, login, password reset, and phone change verification.
- Farmer onboarding with location, preferred language, experience level, goals, and crops grown.
- AI chat agent for crop, fertilizer, weather, and general farming advice.
- Crop image diagnosis:
    - Gemini image triage decides whether an image is a plant, sorghum, enset, a supported crop, or unsupported.
    - Sorghum is routed to AgriRoots' own EfficientNet-B0 PyTorch model.
    - Enset is routed to AgriRoots' own EfficientNet-B0 PyTorch model.
    - Supported non-sorghum, non-enset crops are routed to Kindwise Crop.health.
- Voice:
    - English STT/TTS uses Google Cloud Speech-to-Text and Text-to-Speech.
    - Amharic STT/TTS and Amharic-English translation use Hasab AI.
- Open-Meteo weather, iSDA soil context, SMS Ethiopia OTP delivery, and in-app farm risk alerts.

## Architecture

```text
frontend/                                   React + Vite + Capacitor
backend/                                    FastAPI + SQLAlchemy backend
backend/src/model_server.py
                                            Separate FastAPI service for the sorghum model
backend/src/enset_model_server.py
                                            Separate FastAPI service for the enset model
backend/model/                              PyTorch model files location
```

Runtime layout:

```text
Vercel frontend -> DigitalOcean backend API -> external APIs
                                               |
                                               -> local/private sorghum model server
                                               -> local/private enset model server
```

In production, the frontend calls the public backend API domain. The sorghum and enset model servers run as separate services, and the backend calls them using `SORGHUM_MODEL_SERVER_URL` and `ENSET_MODEL_SERVER_URL`.

## Local Development

### Backend

```bash
cd backend
source .venv/Scripts/activate
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### Sorghum Model Server

Place the model checkpoint at:

```text
backend/model/agriroots_sorghum_efficientnet_b0_best.pt
```

Run:

```bash
cd backend
source .venv/Scripts/activate
python -m uvicorn src.model_server:app --reload --host 127.0.0.1 --port 8001
```

Test:

```bash
curl -X POST "http://127.0.0.1:8001/predict?top_k=3" -F "image=@/path/to/sorghum.jpg"
```

### Enset Model Server

Place the model checkpoint at:

```text
backend/model/enset_efficientnet_b0_final_best.pt
```

Run:

```bash
cd backend
source .venv/Scripts/activate
python -m uvicorn src.enset_model_server:app --reload --host 127.0.0.1 --port 8002
```

Test:

```bash
curl -X POST "http://127.0.0.1:8002/predict?top_k=3" -F "image=@/path/to/enset.jpg"
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Local frontend env:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEBUG=false
```

## Environment Configuration

Do not commit `.env` files, database files, service-account JSON files, or production secrets.

### Backend `.env`

Core:

```env
APP_NAME=AgriRoots Backend
DEBUG=false
DATABASE_URL=sqlite:///./agriroots.db
JWT_SECRET_KEY=replace_with_a_long_random_secret_at_least_16_chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

OTP and SMS:

```env
OTP_EXPIRE_MINUTES=5
OTP_MAX_ATTEMPTS=5
PHONE_CHANGE_COOLDOWN_SECONDS=60
SMS_ETHIOPIA_API_KEY=your_sms_ethiopia_api_key
SMS_ETHIOPIA_BASE_URL=https://smsethiopia.et/api
```

AI and advisory integrations:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash
GEMINI_TIMEOUT_SECONDS=20
ISDA_USERNAME=your_isda_username
ISDA_PASSWORD=your_isda_password
KINDWISE_CROP_HEALTH_API_KEY=your_crop_health_api_key
```

Sorghum model:

```env
SORGHUM_MODEL_PATH=backend/model/agriroots_sorghum_efficientnet_b0_best.pt
SORGHUM_MODEL_SERVER_URL=http://127.0.0.1:8001
SORGHUM_MODEL_SERVER_TIMEOUT_SECONDS=30
PLANT_ID_SORGHUM_THRESHOLD=0.35
PLANT_ID_SUPPORTED_CROP_THRESHOLD=0.40
SORGHUM_CONFIDENT_THRESHOLD=0.60
SORGHUM_UNCERTAIN_THRESHOLD=0.40
```

Enset model:

```env
ENSET_MODEL_PATH=backend/model/enset_efficientnet_b0_final_best.pt
ENSET_MODEL_SERVER_URL=http://127.0.0.1:8002
ENSET_MODEL_SERVER_TIMEOUT_SECONDS=30
PLANT_ID_ENSET_THRESHOLD=0.35
ENSET_CONFIDENT_THRESHOLD=0.60
ENSET_UNCERTAIN_THRESHOLD=0.40
```

Voice:

```env
GOOGLE_CLOUD_PROJECT=your_google_cloud_project_id
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/google-service-account.json
GOOGLE_CLOUD_LOCATION=global
GOOGLE_STT_LANGUAGE_CODE=en-US
GOOGLE_STT_MODEL=latest_short
GOOGLE_TTS_LANGUAGE_CODE=en-US
GOOGLE_TTS_VOICE_NAME=en-US-Chirp3-HD-Aoede
GOOGLE_TTS_AUDIO_ENCODING=MP3
GOOGLE_TTS_SPEAKING_RATE=0.96

HASAB_API_KEY=your_hasab_api_key
HASAB_API_BASE_URL=https://api.hasab.ai/api
HASAB_TIMEOUT_SECONDS=60
HASAB_AMHARIC_LANGUAGE_CODE=amh
HASAB_TTS_AMHARIC_SPEAKER_NAME=Selam
```

Debug-only reset endpoint:

```env
DEBUG_RESET_TOKEN=replace_with_debug_reset_token
```

### Frontend `.env`

Production Vercel env:

```env
VITE_API_BASE_URL=https://api.agriroots.example.com
VITE_DEBUG=false
```

## Deployment

The `example.com` URLs below are placeholders. Configure your own frontend and API domains, then set `VITE_API_BASE_URL` to your deployed API URL.

Example frontend URL for a Vercel deployment:

```text
https://agriroots.example.com/
```

Example backend API URL for a DigitalOcean Ubuntu deployment:

```text
https://api.agriroots.example.com/
```

The sorghum and enset model servers run as separate backend services and are called by the main backend through `SORGHUM_MODEL_SERVER_URL` and `ENSET_MODEL_SERVER_URL`. Both model services should remain private unless deployed behind their own protected endpoints.

SQLite can be used for demos, but PostgreSQL is recommended for production:

```env
DATABASE_URL=postgresql+psycopg2://agriroots_user:strong_password@127.0.0.1:5432/agriroots
```

## Database Notes

The backend uses SQLAlchemy models and creates tables at startup.

Uploaded crop images and voice recordings are not permanently stored by AgriRoots in the current implementation. Chat messages store text/transcripts and metadata.

## Security Notes

- Keep `DEBUG=false` in production.
- Keep the sorghum and enset model servers private unless they are separately protected.
- Use HTTPS for deployed frontend and backend.
- Restrict DigitalOcean firewall ports to SSH, HTTP, and HTTPS.
