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

# OpenAI API (required for transcription and chat functionality)
OPENAI_API_KEY=your-openai-api-key

# Environment
ENVIRONMENT=development
```