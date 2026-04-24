from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import shutil
import uuid
import re
from pathlib import Path
from aligner import align_audio

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
TEMP_DIR = Path("temp_uploads")
INPUTS_DIR = Path("inputs")
OUTPUTS_DIR = Path("outputs")

TEMP_DIR.mkdir(exist_ok=True)
INPUTS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# Store current file_id globally to track if new audio is uploaded
current_file_id = None


def clean_format(text: str) -> str:
    """Clean transcript by removing bullet points and formatting"""
    lines = text.splitlines()
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        line = re.sub(r'^[•\-\*\u2022]+\s*', '', line)
        if line:
            cleaned_lines.append(line)
    
    return "\n\n".join(cleaned_lines)


def update_transcript_files(raw_transcript: str):
    """
    ALWAYS clear and update transcript files with latest content.
    Returns cleaned transcript.
    """
    # Fixed file paths
    raw_path = INPUTS_DIR / "transcript.txt"
    clean_path = INPUTS_DIR / "clean_transcript.txt"
    
    # Clean the transcript
    cleaned_transcript = clean_format(raw_transcript)
    
    # ALWAYS clear and write fresh (overwrite)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_transcript)
    
    with open(clean_path, "w", encoding="utf-8") as f:
        f.write(cleaned_transcript)
    
    print(f"✅ Updated files - Raw: {len(raw_transcript)} chars, Cleaned: {len(cleaned_transcript)} chars")
    
    return cleaned_transcript


def clear_all_data():
    """Clear temp audio and reset file_id"""
    global current_file_id
    
    # Clear temp_uploads folder
    for file in TEMP_DIR.glob("*"):
        try:
            file.unlink()
        except:
            pass
    
    # Reset current_file_id
    current_file_id = None
    
    print("🧹 Cleared all temporary audio data")


@app.get("/")
async def root():
    return {"message": "VTT Generator API is running"}


@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Upload audio file - clears previous audio data"""
    global current_file_id
    
    # Clear previous audio data when new audio is uploaded
    clear_all_data()
    
    if not file.filename.endswith(('.mp3', '.wav', '.m4a')):
        raise HTTPException(400, "Only audio files (MP3, WAV, M4A) are allowed")
    
    # Generate unique filename for temp storage
    current_file_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    file_path = TEMP_DIR / f"{current_file_id}{file_extension}"
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return JSONResponse({
        "file_id": current_file_id,
        "filename": file.filename,
        "message": "Audio uploaded successfully! Previous data cleared."
    })


@app.post("/clean-transcript")
async def clean_transcript_endpoint(transcript: str = Form(...)):
    """Clean transcript - this MUST be called before generating VTT"""
    if not transcript or not transcript.strip():
        raise HTTPException(400, "Transcript cannot be empty")
    
    # Clean the transcript
    cleaned = clean_format(transcript)
    
    # Update the transcript files
    update_transcript_files(transcript)
    
    return JSONResponse({
        "cleaned": cleaned,
        "message": "Transcript cleaned and saved successfully!"
    })


@app.post("/generate-vtt")
async def generate_vtt_endpoint(
    file_id: str = Form(...),
    cleaned_transcript: str = Form(...)
):
    """Generate VTT - ONLY accepts cleaned transcript"""
    global current_file_id
    
    # Verify this is the current active file
    if file_id != current_file_id:
        raise HTTPException(400, "Audio file expired or not found. Please re-upload.")
    
    # Verify cleaned transcript is actually cleaned (has no bullet points)
    if any(bullet in cleaned_transcript[:20] for bullet in ['•', '-', '*', '●', '○']):
        raise HTTPException(400, "Please clean the transcript first before generating VTT")
    
    if not cleaned_transcript or not cleaned_transcript.strip():
        raise HTTPException(400, "Cleaned transcript cannot be empty")
    
    try:
        # Find the audio file
        audio_path = TEMP_DIR / f"{file_id}.*"
        audio_files = list(TEMP_DIR.glob(f"{file_id}.*"))
        if not audio_files:
            raise HTTPException(404, "Audio file not found. Please re-upload.")
        
        audio_path = audio_files[0]
        
        # Generate VTT using the cleaned transcript
        segments = align_audio(str(audio_path), cleaned_transcript)
        
        # Generate VTT content
        vtt_content = ["WEBVTT\n"]
        
        for i, seg in enumerate(segments, 1):
            start_time = format_time(seg['start'])
            end_time = format_time(seg['end'])
            vtt_content.append(f"\n{i}\n{start_time} --> {end_time}\n{seg['text']}")
        
        vtt_string = "\n".join(vtt_content)
        
        # Save VTT file
        vtt_path = OUTPUTS_DIR / "output.vtt"
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(vtt_string)
        
        return JSONResponse({
            "success": True,
            "vtt": vtt_string,
            "segments": segments,
            "chunk_count": len(segments),
            "message": f"✅ Successfully generated {len(segments)} captions!"
        })
    
    except Exception as e:
        raise HTTPException(500, str(e))


def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02}:{mins:02}:{secs:06.3f}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)