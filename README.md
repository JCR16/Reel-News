# Reel News

## Overview

Reel News is a short-form news aggregation platform designed to help readers stay informed while minimizing political bias. The platform synthesizes information from multiple news sources using large language models (LLMs) to generate concise, bias-reduced headlines and summaries.

The project aims to allow readers to explore original source articles, compare perspectives, and bookmark stories for future reference.

Reel News is being developed as a senior capstone project by undergraduate Computer Science students at the University of Nevada, Reno.

## Features

- AI-generated headlines and summaries
- Scrollable news feed and individual story pages
- User accounts and story bookmarking
- Administrative story generation and management
- Revision history, editorial review, and publication
- Story archiving and restoration

## Technology Stack

- **Backend:** Python, Django
- **Frontend:** Django Templates, HTML, CSS, JavaScript
- **Database:** PostgreSQL
- **AI:** Google Gemini
- **Hosting:** Render

## Getting Started

### Installation

From the repository root, create a virtual environment and install the project dependencies.

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment and run:

```bash
pip install -r requirements.txt
```

### Configuration

Copy `backend/.env.example` to `backend/.env` and configure the PostgreSQL connection, Django secret key, and Gemini API key.

The application requires access to a configured Reel News PostgreSQL database.

### Running the Application

From the `backend` directory:

```bash
python manage.py runserver
```

- News feed: http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/

### Testing

```bash
python manage.py test --verbosity 2
```

See [TESTING.md](TESTING.md) for additional testing instructions and documentation.

## Contributors

- Austin Landis
- Adam Santos
- Georgia Guillebeau
- Juan Rivero