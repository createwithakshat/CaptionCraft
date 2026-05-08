# 🎬 CaptionCraft

## What is this?

Upload any audio/video file → Get perfectly timed captions (VTT files) with 100-character limit - made for Articulate Storyline.

## Try it

👉 https://caption-craft-orpin.vercel.app

## Features

| Feature | What it does |
|---------|---------------|
| AI Auto | Transcribes audio automatically using Whisper AI |
| Manual | Use your own transcript - we add timing |
| Video support | Upload MP4, MOV, AVI - audio extracted automatically |
| Live preview | Play audio and watch captions highlight in real time |
| 100-char limit | Splits at punctuation, never exceeds Storyline limit |
| Download | Get VTT file or copy to clipboard |

## How it works
Upload file → AI transcribes OR you paste transcript → Split into 100-char chunks → Add timestamps → Download VTT

text

## Tech stack

- **Frontend:** React, Tailwind CSS, Vercel
- **Backend:** FastAPI, WhisperX, Modal
- **Audio:** FFmpeg

## Run locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app:app --reload

# Frontend
cd frontend  
npm install
npm run dev

Author
Akshat Aswal

⭐ Star if useful 
```