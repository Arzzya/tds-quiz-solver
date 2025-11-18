import os
import json
import asyncio
import httpx
import pandas as pd
import pdfplumber
import io
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TDS Quiz Solver")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store user secrets (in production, use a database)
USER_SECRETS = {
    "roshanbanu0906@gmail.com": "my-super-secret",
    "you@example.com": "my-super-secret"  # Added backup email
}

# Debug: Print configured secrets on startup
print("=== SERVER STARTING ===")
print("Configured emails and secrets:")
for email, secret in USER_SECRETS.items():
    print(f"  {email}: {secret}")
print("=======================")

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str
    submit_url: Optional[str] = None
    attachments: Optional[List[str]] = None

class AnswerSubmission(BaseModel):
    email: str
    secret: str
    url: str
    answer: Any

def verify_secret(email: str, secret: str) -> bool:
    """Verify user secret"""
    print(f"🔐 DEBUG SECRET VERIFICATION:")
    print(f"   Email received: '{email}'")
    print(f"   Secret received: '{secret}'")
    print(f"   Stored secret for this email: '{USER_SECRETS.get(email)}'")
    
    result = USER_SECRETS.get(email) == secret
    print(f"   Verification result: {result}")
    print(f"   All configured emails: {list(USER_SECRETS.keys())}")
    
    return result

async def download_file(url: str) -> Optional[bytes]:
    """Download file from URL with error handling"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return None

def extract_value_sum_from_pdf(pdf_content: bytes, page_number: int = 2) -> Optional[float]:
    """Extract and sum 'value' column from PDF"""
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            # Try specified page, fall back to first page
            target_page = page_number - 1  # 0-indexed
            if target_page >= len(pdf.pages):
                target_page = 0
            
            page = pdf.pages[target_page]
            tables = page.extract_tables()
            
            for table in tables:
                df = pd.DataFrame(table)
                # Find column with 'value' header (case insensitive)
                for col_idx, header in enumerate(df.iloc[0] if len(df) > 0 else []):
                    if header and 'value' in str(header).lower():
                        # Sum numeric values in this column
                        total = 0
                        for row_idx in range(1, len(df)):
                            try:
                                val = float(str(df.iloc[row_idx, col_idx]).replace(',', ''))
                                total += val
                            except (ValueError, TypeError):
                                continue
                        return total if total > 0 else None
        return None
    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        return None

def extract_value_sum_from_csv(csv_content: bytes) -> Optional[float]:
    """Extract and sum 'value' column from CSV"""
    try:
        df = pd.read_csv(io.BytesIO(csv_content))
        if 'value' in df.columns:
            return float(df['value'].sum())
        # Try case insensitive
        for col in df.columns:
            if 'value' in col.lower():
                return float(df[col].sum())
        return None
    except Exception as e:
        logger.error(f"CSV processing error: {e}")
        return None

def extract_value_sum_from_excel(excel_content: bytes) -> Optional[float]:
    """Extract and sum 'value' column from Excel"""
    try:
        df = pd.read_excel(io.BytesIO(excel_content))
        if 'value' in df.columns:
            return float(df['value'].sum())
        for col in df.columns:
            if 'value' in col.lower():
                return float(df[col].sum())
        return None
    except Exception as e:
        logger.error(f"Excel processing error: {e}")
        return None

async def solve_quiz_task(request: QuizRequest) -> Dict[str, Any]:
    """Main quiz solving logic"""
    try:
        answer = None
        processed_attachments = []
        
        # Process attachments if provided
        if request.attachments:
            for attachment_url in request.attachments:
                content = await download_file(attachment_url)
                if content:
                    processed_attachments.append({
                        'url': attachment_url,
                        'size': len(content),
                        'processed': True
                    })
                    
                    # Determine file type and process
                    if attachment_url.lower().endswith('.pdf'):
                        answer = extract_value_sum_from_pdf(content)
                    elif attachment_url.lower().endswith('.csv'):
                        answer = extract_value_sum_from_csv(content)
                    elif attachment_url.lower().endswith(('.xlsx', '.xls')):
                        answer = extract_value_sum_from_excel(content)
                    
                    if answer is not None:
                        break
        
        # If no attachments or couldn't process them, try to fetch from the main URL
        if answer is None:
            content = await download_file(request.url)
            if content:
                # Try to process main URL content
                if request.url.lower().endswith('.pdf'):
                    answer = extract_value_sum_from_pdf(content)
                elif request.url.lower().endswith('.csv'):
                    answer = extract_value_sum_from_csv(content)
                elif request.url.lower().endswith(('.xlsx', '.xls')):
                    answer = extract_value_sum_from_excel(content)
        
        # Prepare submission
        submission_data = AnswerSubmission(
            email=request.email,
            secret=request.secret,
            url=request.url,
            answer=answer if answer is not None else "[COULD NOT COMPUTE]"
        )
        
        # Submit answer (if not example.com)
        submission_result = None
        submit_url = request.submit_url or "https://example.com/submit"
        
        if "example.com" not in submit_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        submit_url,
                        json=submission_data.dict(),
                        timeout=30.0
                    )
                    submission_result = response.json()
            except Exception as e:
                logger.error(f"Submission failed: {e}")
                submission_result = {"error": str(e)}
        
        return {
            "ok": True,
            "answer": answer,
            "submission": submission_data.model_dump(),
            "submission_result": submission_result,
            "processed_attachments": processed_attachments
        }
        
    except Exception as e:
        logger.error(f"Quiz solving error: {e}")
        return {
            "ok": False,
            "reason": str(e)
        }

@app.post("/")
async def solve_quiz(request: QuizRequest, background_tasks: BackgroundTasks):
    """Main quiz solving endpoint"""
    print(f"📨 INCOMING REQUEST:")
    print(f"   Email: {request.email}")
    print(f"   URL: {request.url}")
    
    # Verify secret
    if not verify_secret(request.email, request.secret):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    logger.info(f"Processing quiz for {request.email} - URL: {request.url}")
    
    # Process the quiz
    result = await solve_quiz_task(request)
    
    return result

@app.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    secret: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload file for processing"""
    print(f"📤 UPLOAD REQUEST:")
    print(f"   Email: {email}")
    print(f"   Filename: {file.filename}")
    
    if not verify_secret(email, secret):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    try:
        content = await file.read()
        
        # Determine file type and process
        answer = None
        if file.filename.lower().endswith('.pdf'):
            answer = extract_value_sum_from_pdf(content)
        elif file.filename.lower().endswith('.csv'):
            answer = extract_value_sum_from_csv(content)
        elif file.filename.lower().endswith(('.xlsx', '.xls')):
            answer = extract_value_sum_from_excel(content)
        
        return {
            "ok": True,
            "filename": file.filename,
            "answer": answer,
            "message": f"Processed {file.filename} successfully"
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "tds-quiz-solver"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")