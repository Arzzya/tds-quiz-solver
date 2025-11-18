# TDS LLM Quiz Solver

A FastAPI-based application that automatically solves data analysis quizzes involving data sourcing, preparation, analysis, and visualization.

## Features

- Secure API endpoint with secret verification
- File processing (PDF, CSV, Excel)
- Data analysis and value summation
- Headless browser support (Playwright)
- 3-minute timeout handling for quiz sequences

## API Endpoints

- \POST /\ - Main quiz solving endpoint
- \POST /upload\ - File upload for testing
- \GET /health\ - Health check

## Setup

1. Clone the repository
2. Create virtual environment: \python -m venv venv\
3. Activate venv: \.\venv\Scripts\activate\ (Windows)
4. Install dependencies: \pip install -r requirements.txt\
5. Run: \python app.py\

## License

MIT License
