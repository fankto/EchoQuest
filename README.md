# EchoQuest

EchoQuest is a modern interview transcription and analysis platform that helps researchers, journalists, and professionals extract insights from interviews through AI-powered transcription, analysis, and question answering.

## Features

- 🎙️ **Audio Processing**: Enhance audio quality and transcribe interviews with high accuracy using OpenAI's Whisper
- 🗣️ **Speaker Diarization**: Automatically identify different speakers in the conversation
- 📝 **Questionnaire Management**: Create and manage interview questionnaires
- 🔍 **AI Analysis**: Automatically extract answers to predefined questions
- 💬 **Intelligent Chat**: Converse with your interview transcripts using natural language with OpenAI
- 🔒 **User Management**: Secure authentication and organization-based permissions
- 💰 **Credit System**: Flexible pay-as-you-go pricing model

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.10+ (for backend development)
- OpenAI API key (required for transcription and chat functionality)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/echoquest.git
cd echoquest
```

2. Create a `.env` file in the root directory with the following variables:

```
# Database
POSTGRES_USER=echoquest
POSTGRES_PASSWORD=echoquest
POSTGRES_DB=echoquest

# JWT Authentication
JWT_SECRET=your-super-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# OpenAI API (required for transcription and chat functionality)
OPENAI_API_KEY=your-openai-api-key

# Environment
ENVIRONMENT=development
```

3. Start the application using Docker Compose:

```bash
docker-compose up --build
```

4. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## Development

### Backend Development

The backend is built with FastAPI and SQLAlchemy:

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

### Frontend Development

The frontend is built with Next.js:

```bash
cd frontend
npm install
npm run dev
```

## Architecture

EchoQuest is built with a modern stack:

- **Backend**: FastAPI (Python) with SQLAlchemy ORM
- **Frontend**: Next.js with TailwindCSS and shadcn/ui
- **Database**: PostgreSQL for reliable data storage
- **Vector Database**: Qdrant for transcript embeddings and semantic search
- **Cache**: Redis for session management and caching
- **Speech-to-Text**: AssemblyAI for accurate transcription with speaker diarization
- **Language Processing**: OpenAI API for chat and question answering

## API Documentation

When running the application, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Credit System

EchoQuest uses a credit-based system:

- **Interview Credits**: Each credit allows processing one interview (upload, transcription, analysis)
- **Chat Tokens**: Each interview includes a base amount of chat tokens, with additional tokens available for purchase

## License

This project is licensed under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request