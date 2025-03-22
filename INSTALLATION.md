# EchoQuest Installation Guide

This guide will walk you through the steps to set up the EchoQuest application for development or testing.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** and **Docker Compose**
- **Git**
- **Node.js** (v18+) and **npm** (for frontend development)
- **Python** (v3.10+) and **Poetry** (for backend development)
- **OpenAI API key** for transcription and chat functionality

## Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/echoquest.git
cd echoquest
```

## Step 2: Environment Configuration

1. Create a `.env` file in the project root with the following variables:

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

# OpenAI API (required for transcription and chat)
OPENAI_API_KEY=your-openai-api-key

# Optional: AssemblyAI for alternative transcription
ASSEMBLYAI_API_KEY=your-assemblyai-api-key

# Environment
ENVIRONMENT=development
```

2. Replace `your-openai-api-key` with your actual OpenAI API key.

## Step 3: Build and Start with Docker Compose

For the simplest setup, use Docker Compose to build and start all services:

```bash
docker-compose up --build
```

This will:
- Build the backend and frontend containers
- Start PostgreSQL, Redis, and Qdrant databases
- Set up all required volumes and networks
- Initialize the database with default schema and test data

Once all services are running, you can access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Step 4: Initial Login

After starting the application, you can log in with the default admin account:

- **Email**: admin@example.com
- **Password**: password123

**Note**: This default account is only available in development mode. Change the password immediately or remove it in production.

## Troubleshooting

### Database Connection Issues

If you encounter database connection errors, ensure PostgreSQL is running:

```bash
docker-compose ps
```

If PostgreSQL is not running, check the logs:

```bash
docker-compose logs postgres
```

### OpenAI API Errors

If transcription or chat features aren't working, verify your OpenAI API key:

1. Check if the key is correctly set in the `.env` file
2. Ensure the key has sufficient credits
3. Check if the key has the necessary permissions for the models being used

## Development Workflow

### Backend Development

For backend development, you can run the FastAPI server directly:

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

### Frontend Development

For frontend development, you can run the Next.js development server:

```bash
cd frontend
npm install
npm run dev
```

## Database Migrations

When making changes to the database schema:

```bash
cd backend
poetry run alembic revision --autogenerate -m "Your migration message"
poetry run alembic upgrade head
```

## Additional Resources

- [Official Documentation](https://docs.example.com/echoquest)
- [API Reference](http://localhost:8000/docs)
- [Contributing Guidelines](CONTRIBUTING.md)

## Support

If you encounter any issues, please contact support at support@example.com or open an issue on the GitHub repository.