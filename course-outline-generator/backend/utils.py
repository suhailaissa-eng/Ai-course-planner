import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

def structure_block_segments(block_title, segments):
    types = ["Video", "Reading", "Assignment", "Quiz", "Discussion"]
    video_types = ["Talking head", "Light Board", "Screencast", "Lab Interview"]
    result = []
    video_count = 0

    for i, seg in enumerate(segments[:7]):
        t = types[i % len(types)]
        entry = {
            "segment_title": seg["title"],
            "learning_type": t,
            "includes": [seg["title"]]
        }
        if t == "Video":
            entry["video_type"] = video_types[video_count % len(video_types)]
            video_count += 1
        result.append(entry)
    return result

def export_block_excel(module, block, structured, out_dir="uploads/review"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{module}_{block}.xlsx".replace(" ", "_"))
    rows = []

    for i, seg in enumerate(structured):
        for j, item in enumerate(seg["includes"]):
            rows.append({
                "Module": module if i == 0 and j == 0 else "",
                "Block": block if i == 0 and j == 0 else "",
                "Learning Segment Title": item,
                "Learning Type": seg["learning_type"],
                "Video Type": seg.get("video_type", "")
            })
    pd.DataFrame(rows).to_excel(path, index=False)
    return path

def validate_edited_excel(path):
    try:
        df = pd.read_excel(path)
        required = ["Module", "Block", "Learning Segment Title", "Learning Type", "Video Type"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing column: {col}")
        return df
    except Exception as e:
        print(f"Validation error: {e}")
        return None

def export_final_excel(data, path):
    rows = []
    for d in data:
        module, block = d["module"], d["block"]
        for seg in d["structured_segments"]:
            for s in seg["includes"]:
                rows.append({
                    "Module (LOs)": module,
                    "Blocks (Learning Weeks)": block,
                    "Learning Segment Title": s,
                    "Learning Segment Type": seg["learning_type"],
                    "Video Type": seg.get("video_type", ""),
                    "Video Link": ""
                })
    pd.DataFrame(rows).to_excel(path, index=False)
