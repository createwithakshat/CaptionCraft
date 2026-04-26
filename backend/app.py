from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import shutil
import uuid
import re
import subprocess
from pathlib import Path
from aligner import align_audio
import whisperx
import torch

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
        "http://localhost:3000",
        "https://caption-craft-orpin.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
TEMP_DIR = Path("temp_uploads")
INPUTS_DIR = Path("inputs")
OUTPUTS_DIR = Path("outputs")
AUDIO_EXTRACT_DIR = Path("temp_audio")

TEMP_DIR.mkdir(exist_ok=True)
INPUTS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)
AUDIO_EXTRACT_DIR.mkdir(exist_ok=True)

# Store current file_id globally
current_file_id = None
current_filename = None


def extract_audio_from_video(video_path, output_audio_path):
    """Extract audio from video file using ffmpeg"""
    try:
        command = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_audio_path
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def transcribe_audio_with_whisper(audio_path):
    """Transcribe audio using WhisperX"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load model
    model = whisperx.load_model("base", device, compute_type="float32")
    
    # Transcribe
    result = model.transcribe(audio_path)
    
    # Get the transcribed text
    transcribed_text = " ".join([seg['text'] for seg in result['segments']])
    
    return transcribed_text, result['segments']


def clean_format(text: str) -> str:
    """Clean transcript by removing bullet points and formatting"""
    lines = text.splitlines()
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        line = re.sub(r'^[•\-\*\u2022]+\s*', '', line)
        line = re.sub(r'^\d+[\.\)]\s*', '', line)
        if line:
            cleaned_lines.append(line)
    
    return " ".join(cleaned_lines)


def update_transcript_files(raw_transcript: str):
    """Clear and update transcript files with latest content"""
    raw_path = INPUTS_DIR / "transcript.txt"
    clean_path = INPUTS_DIR / "clean_transcript.txt"
    
    cleaned_transcript = clean_format(raw_transcript)
    
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_transcript)
    
    with open(clean_path, "w", encoding="utf-8") as f:
        f.write(cleaned_transcript)
    
    return cleaned_transcript


def clear_all_data():
    """Clear temp files and reset"""
    global current_file_id, current_filename
    
    for file in TEMP_DIR.glob("*"):
        try:
            file.unlink()
        except:
            pass
    
    for file in AUDIO_EXTRACT_DIR.glob("*"):
        try:
            file.unlink()
        except:
            pass
    
    current_file_id = None
    current_filename = None


@app.get("/")
async def root():
    return {"message": "VTT Generator API is running - Supports manual transcript or AI auto-transcription"}


@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload audio or video file"""
    global current_file_id, current_filename
    
    clear_all_data()
    
    file_extension = Path(file.filename).suffix.lower()
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v']
    audio_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
    
    if file_extension not in video_extensions + audio_extensions:
        raise HTTPException(400, f"Unsupported format. Supported: {', '.join(video_extensions + audio_extensions)}")
    
    current_file_id = str(uuid.uuid4())
    current_filename = file.filename
    original_path = TEMP_DIR / f"{current_file_id}_original{file_extension}"
    
    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    audio_path_for_alignment = None
    
    if file_extension in video_extensions:
        audio_path_for_alignment = AUDIO_EXTRACT_DIR / f"{current_file_id}_audio.wav"
        success = extract_audio_from_video(original_path, audio_path_for_alignment)
        if not success:
            raise HTTPException(500, "Failed to extract audio from video. Make sure FFmpeg is installed.")
        
        return JSONResponse({
            "file_id": current_file_id,
            "filename": file.filename,
            "type": "video",
            "message": f"Video uploaded! Audio extracted successfully."
        })
    
    else:
        audio_path_for_alignment = original_path
        return JSONResponse({
            "file_id": current_file_id,
            "filename": file.filename,
            "type": "audio",
            "message": "Audio uploaded successfully!"
        })


@app.get("/get-audio/{file_id}")
async def get_audio(file_id: str):
    """Get the audio stream for preview"""
    audio_files = list(AUDIO_EXTRACT_DIR.glob(f"{file_id}_audio.wav"))
    if audio_files:
        return FileResponse(audio_files[0], media_type="audio/wav")
    
    original_files = list(TEMP_DIR.glob(f"{file_id}_original.*"))
    for file in original_files:
        if file.suffix.lower() in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
            return FileResponse(file, media_type="audio/mpeg")
    
    raise HTTPException(404, "Audio not found")


@app.post("/auto-transcribe")
async def auto_transcribe(file_id: str = Form(...)):
    """Automatically transcribe audio using Whisper"""
    global current_file_id
    
    if file_id != current_file_id:
        raise HTTPException(400, "File expired. Please re-upload.")
    
    try:
        # Find the audio file
        audio_path = None
        
        extracted_audio = list(AUDIO_EXTRACT_DIR.glob(f"{file_id}_audio.wav"))
        if extracted_audio:
            audio_path = extracted_audio[0]
        else:
            original_files = list(TEMP_DIR.glob(f"{file_id}_original.*"))
            for file in original_files:
                if file.suffix.lower() in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
                    audio_path = file
                    break
        
        if not audio_path:
            raise HTTPException(404, "Audio file not found")
        
        # Transcribe with Whisper
        transcribed_text, segments_data = transcribe_audio_with_whisper(str(audio_path))
        
        # Clean the transcribed text
        cleaned_transcript = clean_format(transcribed_text)
        
        # Save to files
        update_transcript_files(transcribed_text)
        
        return JSONResponse({
            "success": True,
            "transcript": transcribed_text,
            "cleaned_transcript": cleaned_transcript,
            "segments_data": segments_data,
            "message": "✅ Auto-transcription completed!"
        })
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(500, str(e))


@app.post("/clean-transcript")
async def clean_transcript_endpoint(transcript: str = Form(...)):
    """Clean transcript - prepares it for VTT generation"""
    if not transcript or not transcript.strip():
        raise HTTPException(400, "Transcript cannot be empty")
    
    cleaned = clean_format(transcript)
    update_transcript_files(transcript)
    
    return JSONResponse({
        "cleaned": cleaned,
        "message": "Transcript processed successfully!"
    })


@app.post("/generate-vtt")
async def generate_vtt_endpoint(
    file_id: str = Form(...),
    cleaned_transcript: str = Form(...)
):
    """Generate VTT from cleaned transcript"""
    global current_file_id
    
    if file_id != current_file_id:
        raise HTTPException(400, "File expired. Please re-upload.")
    
    if not cleaned_transcript or not cleaned_transcript.strip():
        raise HTTPException(400, "Transcript cannot be empty.")
    
    try:
        # Find the audio file
        audio_path = None
        
        extracted_audio = list(AUDIO_EXTRACT_DIR.glob(f"{file_id}_audio.wav"))
        if extracted_audio:
            audio_path = extracted_audio[0]
        else:
            original_files = list(TEMP_DIR.glob(f"{file_id}_original.*"))
            for file in original_files:
                if file.suffix.lower() in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
                    audio_path = file
                    break
        
        if not audio_path:
            raise HTTPException(404, "Audio file not found")
        
        # Generate VTT
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
            "message": f"✅ Generated {len(segments)} captions!"
        })
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(500, str(e))


def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02}:{mins:02}:{secs:06.3f}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)