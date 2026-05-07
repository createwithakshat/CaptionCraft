import modal
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess
import tempfile
import shutil
from pathlib import Path
import uuid
import re
import os

# Create a Modal image with all dependencies
image = modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg").pip_install(
    "fastapi==0.104.1",
    "uvicorn==0.24.0",
    "python-multipart==0.0.6",
    "whisperx==3.1.1",
    "torch==2.1.0",
    "pydub==0.25.1",
    "torchaudio==2.1.0"
)

# Create a Modal app
app = modal.App("captioncraft-backend", image=image)

# Define the FastAPI web endpoint
@app.function(
    scaledown_window=300,
    memory=2048,  # 2GB RAM for Whisper!
    cpu=2.0
)
@modal.asgi_app()
def fastapi_app():
    web_app = FastAPI(title="CaptionCraft API")
    
    # CORS middleware - allow your Vercel frontend
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "https://caption-craft-orpin.vercel.app",
            "https://captioncraft-frontend.vercel.app"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Clean format function
    def clean_format(text: str) -> str:
        lines = text.splitlines()
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            line = re.sub(r'^[•\-\*\u2022]+\s*', '', line)
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            if line:
                cleaned_lines.append(line)
        return " ".join(cleaned_lines)
    
    # Store uploaded files temporarily
    temp_files = {}
    
    @web_app.get("/")
    async def root():
        return {"message": "CaptionCraft API is running on Modal!"}
    
    @web_app.post("/upload-file")
    async def upload_file(file: UploadFile = File(...)):
        file_id = str(uuid.uuid4())
        temp_path = Path(tempfile.gettempdir()) / f"{file_id}_{file.filename}"
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        temp_files[file_id] = {"path": str(temp_path), "filename": file.filename}
        return JSONResponse({
            "file_id": file_id,
            "filename": file.filename,
            "type": "video" if file.filename.endswith(('.mp4', '.mov', '.avi', '.mkv')) else "audio",
            "message": "File uploaded successfully!"
        })
    
    @web_app.get("/get-audio/{file_id}")
    async def get_audio(file_id: str):
        from fastapi.responses import FileResponse
        file_info = temp_files.get(file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            raise HTTPException(404, "File not found")
        return FileResponse(file_info["path"], media_type="audio/mpeg")
    
    @web_app.post("/clean-transcript")
    async def clean_transcript_endpoint(transcript: str = Form(...)):
        cleaned = clean_format(transcript)
        return JSONResponse({"cleaned": cleaned, "message": "Transcript processed!"})
    
    @web_app.post("/generate-vtt")
    async def generate_vtt_endpoint(file_id: str = Form(...), cleaned_transcript: str = Form(...)):
        file_info = temp_files.get(file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            raise HTTPException(404, "File not found")
        
        # Import WhisperX inside the function (loads only when called)
        import whisperx
        import torch
        
        # Transcribe with WhisperX using tiny model (faster, less memory)
        device = "cpu"
        model = whisperx.load_model("tiny", device, compute_type="float32")
        result = model.transcribe(file_info["path"])
        
        # Use the user's cleaned transcript
        if cleaned_transcript and cleaned_transcript.strip():
            total_duration = result["segments"][-1]["end"] if result["segments"] else 10
            segments = []
            total_chars = len(cleaned_transcript)
            current_pos = 0
            
            # Split into 100-character chunks
            while current_pos < total_chars:
                chunk_end = min(current_pos + 100, total_chars)
                segment = cleaned_transcript[current_pos:chunk_end].strip()
                if segment:
                    start_time = (current_pos / total_chars) * total_duration
                    end_time = (chunk_end / total_chars) * total_duration
                    segments.append({
                        "text": segment,
                        "start": start_time,
                        "end": end_time
                    })
                current_pos = chunk_end
        else:
            # Use Whisper's transcription
            segments = []
            for seg in result["segments"]:
                segments.append({
                    "text": seg["text"].strip(),
                    "start": seg["start"],
                    "end": seg["end"]
                })
        
        # Generate VTT content
        def format_time(seconds):
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hrs:02}:{mins:02}:{secs:06.3f}"
        
        vtt_lines = ["WEBVTT\n"]
        for i, seg in enumerate(segments, 1):
            vtt_lines.append(f"\n{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{seg['text']}")
        
        vtt_string = "\n".join(vtt_lines)
        
        return JSONResponse({
            "success": True,
            "vtt": vtt_string,
            "segments": segments,
            "chunk_count": len(segments),
            "message": f"✅ Generated {len(segments)} captions!"
        })
    
    return web_app