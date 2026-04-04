import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import get_connection
from src.memory.rag import index_resume
from src.services.text_extract import extract_text

router = APIRouter(prefix="/api")


class ExtractTextRequest(BaseModel):
    resume_id: int
    file_path: str


@router.post("/extract-text")
async def extract_resume_text(req: ExtractTextRequest):
    try:
        text = extract_text(req.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    conn = get_connection()
    conn.execute(
        "UPDATE resumes SET extracted_text = ? WHERE id = ?",
        (text, req.resume_id),
    )
    conn.commit()

    row = conn.execute(
        "SELECT name FROM resumes WHERE id = ?", (req.resume_id,)
    ).fetchone()
    conn.close()

    resume_name = row["name"] if row else f"Resume {req.resume_id}"
    index_resume(req.resume_id, resume_name, text)

    return {"resume_id": req.resume_id, "char_count": len(text)}
