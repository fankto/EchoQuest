# EchoQuest Project Structure

This document provides an overview of the EchoQuest project structure to help developers understand the organization of the codebase.

## Root Directory

```
echoquest/
├── .env.example           # Example environment variables
├── docker-compose.yml     # Docker compose configuration
├── README.md              # Project documentation
├── INSTALLATION.md        # Installation guide
├── LICENSE                # License information
├── backend/               # Backend application (FastAPI)
└── frontend/              # Frontend application (Next.js)
```

## Backend Structure

```
backend/
├── Dockerfile             # Docker configuration for backend
├── pyproject.toml         # Python dependencies and project metadata
├── poetry.lock            # Poetry lock file for dependencies
├── alembic/               # Database migration scripts
└── app/                   # Application source code
    ├── main.py            # Application entry point
    ├── api/               # API routes and endpoints
    │   ├── deps.py        # Dependency injection
    │   └── routes/        # API route modules
    ├── core/              # Core application code
    │   ├── config.py      # Application configuration
    │   └── exceptions.py  # Custom exceptions
    ├── crud/              # Database CRUD operations
    ├── db/                # Database configuration
    │   ├── base_class.py  # SQLAlchemy base class
    │   ├── init_db.py     # Database initialization
    │   └── session.py     # Database session management
    ├── models/            # SQLAlchemy ORM models
    ├── schemas/           # Pydantic schemas for validation
    └── services/          # Business logic services
        ├── chat_service.py        # Chat functionality
        ├── file_service.py        # File management
        ├── qdrant_service.py      # Vector database operations
        ├── token_service.py       # Authentication token handling
        └── transcription_service.py # Audio transcription
```

## Frontend Structure

```
frontend/
├── Dockerfile             # Docker configuration for frontend
├── package.json           # Node.js dependencies and scripts
├── next.config.js         # Next.js configuration
├── tailwind.config.js     # Tailwind CSS configuration
├── postcss.config.js      # PostCSS configuration
├── tsconfig.json          # TypeScript configuration
├── public/                # Static assets
└── src/                   # Application source code
    ├── app/               # Next.js app router
    │   ├── layout.tsx     # Root layout component
    │   ├── page.tsx       # Home page component
    │   ├── auth/          # Authentication pages
    │   ├── interviews/    # Interview pages
    │   ├── questionnaires/ # Questionnaire pages
    │   └── credits/       # Credits/pricing pages
    ├── components/        # React components
    │   ├── ui/            # UI components (buttons, cards, etc.)
    │   ├── auth/          # Authentication components
    │   ├── dashboard/     # Dashboard components
    │   └── interview/     # Interview-specific components
    ├── hooks/             # Custom React hooks
    ├── lib/               # Utility functions
    │   ├── api-client.ts  # API client with authentication
    │   ├── utils.ts       # General utilities
    │   └── format.ts      # Formatting utilities
    ├── styles/            # Global styles
    └── types/             # TypeScript types
```

## Key Components

### Backend Components

1. **API Routes**
   - `auth.py` - Authentication endpoints
   - `interviews.py` - Interview management
   - `chat.py` - Chat functionality
   - `credits.py` - Credit management
   - `questionnaires.py` - Questionnaire management

2. **Services**
   - `TranscriptionService` - Audio processing and transcription
   - `ChatService` - Chat functionality using OpenAI
   - `QdrantService` - Vector search for transcript segments
   - `TokenService` - JWT token management

3. **Database Models**
   - `User` - User information
   - `Interview` - Interview data
   - `Questionnaire` - Questionnaire templates
   - `Transaction` - Credit and token transactions

### Frontend Components

1. **Pages**
   - Dashboard - Overview of interviews and statistics
   - Interview Detail - View and interact with interviews
   - Chat Interface - Chat with interview transcripts
   - Credits - Purchase and manage credits

2. **Components**
   - `TranscriptViewer` - Display and edit transcripts
   - `ChatInterface` - Chat with interviews
   - `AudioPlayer` - Play interview audio
   - `CreditSummary` - Display credit/token information

3. **Hooks**
   - `useAuth` - Authentication state management
   - `useInterview` - Interview data fetching
   - `useChat` - Chat functionality

## Data Flow

1. **Interview Processing**
   - Upload audio file
   - Audio preprocessing (noise reduction, etc.)
   - Transcription with speaker diarization
   - Text chunking and indexing in Qdrant
   - Question extraction and answering

2. **Chat Functionality**
   - User submits question
   - Relevant transcript chunks retrieved via vector search
   - Context assembled with transcript chunks
   - Response generated with LLM
   - Token usage tracked and deducted

3. **Credit System**
   - User purchases interview credits
   - Credits deducted when processing interviews
   - Chat tokens allocated per interview
   - Additional chat tokens can be purchased

## Extensibility Points

1. **Alternative Transcription Services**
   - The architecture supports plugging in different transcription services

2. **Custom Analysis Modules**
   - New analysis modules can be added to extract different types of insights

3. **Additional Payment Providers**
   - The payment system is designed to accommodate multiple providers

4. **Organization and Team Features**
   - The data model supports organization-based access control