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
=======
![License: Custom Non-Commercial](https://img.shields.io/badge/License-Custom%20Non--Commercial-red.svg)
[![Project Status: Alpha](https://img.shields.io/badge/Project%20Status-Alpha-yellow.svg)](README.md)

EchoQuest is a tool designed to streamline the process of conducting, transcribing, and analyzing semi-guided interviews. This application helps interviewers manage questionnaires, process audio recordings, generate transcriptions, and automatically answer predefined questions based on the interview content.

![Application Dashboard](images/dashboard.png)

## Table of Contents
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Questionnaire Management**: Create, edit, and manage interview questionnaires.
- **Audio Processing**: Upload and process audio files for improved quality.
- **Automatic Transcription**: Generate accurate transcriptions from processed audio files.
- **Question Answering**: Automatically answer predefined questions based on the interview transcription.
- **Interview Management**: Organize and track multiple interviews and their progress.
- **User-friendly Interface**: Intuitive web-based interface for easy navigation and management.

## Technologies Used

- **Backend**: FastAPI (Python)
- **Frontend**: React with Chakra UI
- **Database**: SQLite with SQLAlchemy ORM
- **Audio Processing**: PyTorch, Torchaudio
- **Transcription**: Transformers (Whisper model)
- **Question Answering**: Custom LLM-based system

## Prerequisites
Before installing EchoQuest, ensure you have the following:

* Docker and Docker Compose installed on your system
* A GPU with at least 10GB VRAM
* At least 15GB of free disk space
* A Hugging Face account with access to the following models:
    * `meta-llama/Llama-3.1-8B-Instruct`: Used for question extraction and answering
    * `openai/whisper-large-v3-turbo`: Used for audio transcription
    * `pyannote/speaker-diarization-3.1`: Used for speaker diarization

You need to request access to these models on the Hugging Face website and obtain an API token.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/fankto/EchoQuest.git
   cd EchoQuest
   ```

2. Set up environment variables:
   Create a `.env` file in the backend directory with the following content:
   ```
   HF_TOKEN=your_huggingface_token_here
   ```
   Replace `your_huggingface_token_here` with your actual Hugging Face API token.

3. Start the application:
* For first-time setup:
  ```
  docker-compose up --build
  ```
  This will build the Docker images and start the containers.

* For subsequent starts:
  ```
  docker-compose up
  ```
  This will start the existing containers.

* To stop the application:
  ```
  docker-compose down
  ```

4. Once the containers are running, you can access the application at `http://localhost:3000`.

## Usage

### Creating a Questionnaire

1. Navigate to "New Questionnaire" in the sidebar.
2. Enter the questionnaire title and content.
3. The system will automatically extract relevant questions.

![Create Questionnaire](images/create_questionnaire.png)

### Starting an Interview

1. Click on "New Interview" in the sidebar.
2. Select a questionnaire and enter interviewee details.
3. Upload audio file(s) of the interview.

![New Interview](images/create_interview.png)

### Processing and Transcribing

1. In the interview details page, click "Process Audio" to enhance audio quality.
2. After processing, click "Transcribe" to generate the interview transcription.

![Process and Transcribe](images/process_transcribe.png)

### Generating Answers

1. Once transcription is complete, click "Generate Answers" to automatically answer predefined questions.
2. Review the generated answers in the interview details page.

![Generated Answers](images/question_answering.png)

### Reviewing and Managing Interviews

- Use the dashboard to view all interviews and their statuses.
- Click on an interview to view details, edit metadata, or delete the interview.

![Interview Management](images/all_interviews.png)

## Support My Work

If you find EchoQuest useful and want to help me keep developing innovative, open-source tools, consider supporting me by buying me a token. Your support helps cover development costs and allows me to create more projects like this!

[Buy me a token!](https://buymeacoffee.com/fankto)

Or, scan the QR code below to contribute:

![Buy me a token QR Code](images/buymeatokenqr.png)

Thank you for your support! It truly makes a difference.

## Architecture

EchoQuest follows a client-server architecture:

- **Frontend**: React-based single-page application
- **Backend**: FastAPI server handling API requests
- **Database**: SQLite database for storing questionnaires, interviews, and related data
- **Audio Processing**: PyTorch-based pipeline for enhancing audio quality
- **Transcription**: Utilizes the Whisper model for accurate speech-to-text conversion
- **Question Answering**: Custom LLM-based system for generating answers from transcriptions

![System Architecture](images/architecture.png)

## Contributing

Contributions to EchoQuest are welcome! Please follow these steps:

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature-name`
3. Make your changes and commit them: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Submit a pull request

## License
This project is licensed under a Custom Non-Commercial, Contribution-Based License.

### Key Points:
- **Private, non-commercial use** of this tool is permitted.
- **Modifications or enhancements** must be contributed to this project (e.g., through pull requests) to be approved by the project maintainer.
- **Commercial use** and creating derivative works for redistribution outside of this project are prohibited.
- **Contact for Commercial Use**: Companies or individuals interested in commercial use should contact Tobias Fankhauser on [LinkedIn](https://www.linkedin.com/in/tobias-fankhauser-b536a0b7) for case-by-case consideration.

For full details, please refer to the [LICENSE](LICENSE) file.

### Third-Party Licenses
This project uses various third-party models and libraries that are subject to their own licenses:
- **Llama model from Meta**: Refer to its [license terms on Hugging Face](https://huggingface.co/meta-llama).
- **Whisper model from OpenAI**: Refer to its [license terms on Hugging Face](https://huggingface.co/openai-whisper).
- **Speaker Diarization model from PyAnnote**: Refer to its [license terms on Hugging Face](https://huggingface.co/pyannote).

Please check each model's specific license terms for their usage restrictions.

## Contributing
We welcome contributions that enhance the tool! Please submit a pull request for any proposed changes or additions. All contributions must comply with the Custom Non-Commercial, Contribution-Based License outlined in the [LICENSE](LICENSE) file.

### Contributor License Agreement (CLA)
By contributing, you agree to the terms outlined in the [CLA](CLA.md). This agreement ensures that all contributions can be used in any future version of the project, including potential commercial versions. Please read the CLA before submitting your pull request.
