from fastapi import FastAPI, File, UploadFile, Body, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import os, shutil
from sentence_transformers import SentenceTransformer, util
from parsers import extract_modules_blocks_from_docx, parse_pptx, parse_pdf, parse_docx
from utils import structure_block_segments, export_block_excel, validate_edited_excel, export_final_excel
import pandas as pd
from docx import Document
import fitz  # PyMuPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
from pathlib import Path


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
model = SentenceTransformer("all-MiniLM-L6-v2")
all_block_outputs = []

@app.post("/generate-outline")
async def generate_outline(
    plan: UploadFile = File(...),
    slides: List[UploadFile] = File([]),
    assignments: List[UploadFile] = File([])
):
    plan_path = os.path.join(UPLOAD_DIR, plan.filename)
    with open(plan_path, "wb") as f:
        shutil.copyfileobj(plan.file, f)

    module_data = extract_modules_blocks_from_docx(plan_path)
    all_segments = []

    for slide in slides:
        ext = os.path.splitext(slide.filename)[-1].lower()
        path = os.path.join(UPLOAD_DIR, slide.filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(slide.file, f)

        if ext == ".pptx":
            all_segments.extend(parse_pptx(path))
        elif ext == ".pdf":
            all_segments.extend(parse_pdf(path))
        elif ext == ".docx":
            all_segments.extend(parse_docx(path))

    global all_block_outputs
    all_block_outputs = []

    for entry in module_data:
        module = entry["module"]
        for block in entry["blocks"]:
            block_emb = model.encode(block, convert_to_tensor=True)
            scored = []
            for seg in all_segments:
                combined = f"{seg['title']} {seg['summary']}"
                emb = model.encode(combined, convert_to_tensor=True)
                score = util.cos_sim(block_emb, emb).item()
                scored.append((score, seg))

            top = sorted(scored, key=lambda x: x[0], reverse=True)[:15]
            top_segs = [s for _, s in top]

            structured = structure_block_segments(block, top_segs)
            excel_path = export_block_excel(module, block, structured)
            all_block_outputs.append({
                "module": module,
                "block": block,
                "structured_segments": structured
            })

    formatted_modules = []
    for entry in all_block_outputs:
        mod = next((m for m in formatted_modules if m["module_title"] == entry["module"]), None)
        if not mod:
            mod = {"module_title": entry["module"], "blocks": []}
            formatted_modules.append(mod)
        mod["blocks"].append({
            "block_title": entry["block"],
            "segments": entry["structured_segments"]
        })

    return {"modules": formatted_modules}

@app.post("/finalize-outline")
async def finalize_outline(selected_modules: List[Dict] = Body(...)):
    try:
        output_path = os.path.join(UPLOAD_DIR, "final_course_outline.xlsx")
        rows = []
        for mod in selected_modules:
            module_title = mod["module_title"]
            for block in mod["blocks"]:
                block_title = block["block_title"]
                for seg in block["segments"]:
                    rows.append({
                        "Module (LOs)": module_title,
                        "Blocks (Learning Weeks)": block_title,
                        "Learning Segment Title": seg["segment_title"],
                        "Learning Segment Type": seg["learning_type"],
                        "Video Type": seg.get("video_type", ""),
                        "Video Link": ""
                    })

        pd.DataFrame(rows).to_excel(output_path, index=False)

        return {
            "message": "Final Excel outline created!",
            "download_url": "/download-final-excel"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/download-final-excel")
async def download_final_excel():
    path = os.path.join(UPLOAD_DIR, "final_course_outline.xlsx")
    return FileResponse(
        path,
        filename="Final_Course_Outline.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
