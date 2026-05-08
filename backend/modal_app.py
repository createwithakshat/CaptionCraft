import modal
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import tempfile
import shutil
from pathlib import Path
import uuid
import re
import os

# Create a Modal image with all dependencies
# Create a Modal image with all dependencies
image = modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg").pip_install(
    "fastapi==0.104.1",
    "uvicorn==0.24.0",
    "python-multipart==0.0.6",
    "whisperx",
    "torch>=2.4.0",
    "torchaudio>=2.4.0",
    "pydub==0.25.1",
    "numpy>=1.26.0"
)

# Create a Modal app
app = modal.App("captioncraft-backend", image=image)

# Define the FastAPI web endpoint
@app.function(
    scaledown_window=300,
    memory=2048,
    cpu=2.0
)
@modal.asgi_app()
def fastapi_app():
    web_app = FastAPI(title="CaptionCraft API")
    
    # CORS middleware - allow all your frontend URLs
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "https://caption-craft-orpin.vercel.app",
            "https://captioncraft-frontend.vercel.app",
            "*"  # Allow all for testing
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
        
        file_extension = file.filename.split('.')[-1].lower()
        is_video = file_extension in ['mp4', 'mov', 'avi', 'mkv', 'webm']
        
        return JSONResponse({
            "file_id": file_id,
            "filename": file.filename,
            "type": "video" if is_video else "audio",
            "message": "File uploaded successfully!"
        })
    
    @web_app.get("/get-audio/{file_id}")
    async def get_audio(file_id: str):
        file_info = temp_files.get(file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            raise HTTPException(404, "File not found")
        return FileResponse(file_info["path"], media_type="audio/mpeg")
    
    @web_app.post("/clean-transcript")
    async def clean_transcript_endpoint(transcript: str = Form(...)):
        if not transcript or not transcript.strip():
            raise HTTPException(400, "Transcript cannot be empty")
        
        cleaned = clean_format(transcript)
        
        # Save to files (optional)
        inputs_dir = Path("/tmp/inputs")
        inputs_dir.mkdir(exist_ok=True)
        
        with open(inputs_dir / "transcript.txt", "w", encoding="utf-8") as f:
            f.write(transcript)
        with open(inputs_dir / "clean_transcript.txt", "w", encoding="utf-8") as f:
            f.write(cleaned)
        
        return JSONResponse({
            "cleaned": cleaned,
            "message": "Transcript processed successfully!"
        })
    
    @web_app.post("/auto-transcribe")
    async def auto_transcribe(file_id: str = Form(...)):
        file_info = temp_files.get(file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            raise HTTPException(404, "File not found")
        
        try:
            # Import WhisperX inside the function
            import whisperx
            import torch
            
            # Load model (using tiny for speed and memory)
            device = "cpu"
            model = whisperx.load_model("tiny", device, compute_type="float32")
            
            # Transcribe
            result = model.transcribe(file_info["path"])
            
            # Get full transcribed text
            transcribed_text = " ".join([seg["text"] for seg in result["segments"]])
            
            # Clean the transcript
            cleaned = clean_format(transcribed_text)
            
            return JSONResponse({
                "success": True,
                "transcript": transcribed_text,
                "cleaned_transcript": cleaned,
                "segments_data": result["segments"],
                "message": "✅ Auto-transcription completed!"
            })
        except Exception as e:
            raise HTTPException(500, f"Transcription failed: {str(e)}")
    
    @web_app.post("/generate-vtt")
    async def generate_vtt_endpoint(
        file_id: str = Form(...),
        cleaned_transcript: str = Form(...)
    ):
        file_info = temp_files.get(file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            raise HTTPException(404, "File not found")
        
        if not cleaned_transcript or not cleaned_transcript.strip():
            raise HTTPException(400, "Transcript cannot be empty")
        
        try:
            # Import WhisperX for timing if needed
            import whisperx
            import torch
            
            # Get audio duration using whisperx
            device = "cpu"
            model = whisperx.load_model("tiny", device, compute_type="float32")
            result = model.transcribe(file_info["path"])
            
            total_duration = result["segments"][-1]["end"] if result["segments"] else 10
            
            # Split cleaned transcript into 100-character chunks
            segments = []
            total_chars = len(cleaned_transcript)
            current_pos = 0
            
            def find_split_point(text, max_chars):
                if len(text) <= max_chars:
                    return len(text)
                
                # Try to split at punctuation
                for punct in ['. ', '! ', '? ', ', ', '; ', ': ', ' ']:
                    pos = text.rfind(punct, 0, max_chars)
                    if pos != -1:
                        return pos + len(punct)
                return max_chars
            
            while current_pos < total_chars:
                remaining = cleaned_transcript[current_pos:]
                chunk_end = find_split_point(remaining, 100)
                segment = remaining[:chunk_end].strip()
                
                if segment:
                    start_time = (current_pos / total_chars) * total_duration
                    end_time = ((current_pos + chunk_end) / total_chars) * total_duration
                    segments.append({
                        "text": segment,
                        "start": start_time,
                        "end": end_time
                    })
                current_pos += chunk_end
            
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
        except Exception as e:
            raise HTTPException(500, f"Generation failed: {str(e)}")
    
    return web_app