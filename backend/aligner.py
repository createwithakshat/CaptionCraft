import whisperx
import torch
import re
from audio_utils import normalize_audio, detect_silences


def clean_transcript(text):
    """Clean transcript but preserve ALL original text"""
    # Remove bullet points and numbering
    text = re.sub(r'^[\•\-\*\–\—]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+[\.\)]\s*', '', text, flags=re.MULTILINE)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_into_chunks(text, max_chars=100):
    """
    Split text into chunks of max_chars characters.
    Prioritizes splitting at punctuation, but will split at any word if needed.
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        
        # Try to find best split point within max_chars
        split_at = max_chars
        
        # Priority 1: Look for sentence boundaries (. ! ?)
        for punct in ['. ', '! ', '? ']:
            pos = remaining.rfind(punct, 0, max_chars)
            if pos != -1:
                split_at = pos + len(punct)  # Include the punctuation and space
                break
        
        # Priority 2: Look for other punctuation with space (, ; : )
        if split_at == max_chars:
            for punct in [', ', '; ', ': ']:
                pos = remaining.rfind(punct, 0, max_chars)
                if pos != -1:
                    split_at = pos + len(punct)
                    break
        
        # Priority 3: Look for any space
        if split_at == max_chars:
            pos = remaining.rfind(' ', 0, max_chars)
            if pos != -1:
                split_at = pos + 1  # Include the space
        
        # Priority 4: No space found - force split at max_chars
        # (This shouldn't happen with normal text, but just in case)
        
        chunk = remaining[:split_at].strip()
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    
    return chunks


def align_audio(audio_path, transcript):
    """
    Align EXACT client transcript with audio.
    Chunks are created to be as close to 100 chars as possible.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Normalize audio
    audio_path = normalize_audio(audio_path)
    
    # Load WhisperX model (ONLY for timing)
    model = whisperx.load_model("base", device, compute_type="float32")
    result = model.transcribe(audio_path)
    
    # Load alignment model
    model_a, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    
    # Align words - THIS GIVES US TIMING ONLY
    aligned = whisperx.align(
        result["segments"], model_a, metadata, audio_path, device
    )
    
    whisper_word_segments = aligned.get("word_segments", [])
    
    if not whisper_word_segments:
        return []
    
    # Clean client's EXACT transcript
    cleaned_transcript = clean_transcript(transcript)
    
    # FIRST: Split the transcript into character-based chunks (max 100 chars)
    text_chunks = split_into_chunks(cleaned_transcript, 100)
    
    # For each text chunk, we need to find its start and end time in the audio
    timed_chunks = []
    
    # Get total audio duration from whisper
    total_duration = whisper_word_segments[-1].get("end", 30.0)
    
    # Calculate character position of each chunk in the full text
    full_text = cleaned_transcript
    current_pos = 0
    
    for chunk_text in text_chunks:
        # Find where this chunk appears in the full text
        chunk_start_pos = full_text.find(chunk_text, current_pos)
        
        if chunk_start_pos == -1:
            # Fallback: use position-based timing
            chunk_start_pos = current_pos
        
        # Calculate timing based on character position proportion
        start_ratio = chunk_start_pos / len(full_text)
        end_ratio = (chunk_start_pos + len(chunk_text)) / len(full_text)
        
        start_time = start_ratio * total_duration
        end_time = end_ratio * total_duration
        
        timed_chunks.append({
            'start': start_time,
            'end': end_time,
            'text': chunk_text
        })
        
        current_pos = chunk_start_pos + len(chunk_text)
    
    # Refine timing using whisper word timestamps if available
    if whisper_word_segments:
        # Create a list of all words with their character positions
        # This is an approximation since whisper text differs from client text
        whisper_full_text = ' '.join([seg['word'] for seg in whisper_word_segments])
        
        for chunk in timed_chunks:
            # Find where this chunk's text approximately occurs in whisper text
            # Use a simple sliding window approach
            chunk_words = chunk['text'].split()
            
            best_start_idx = 0
            best_end_idx = 0
            best_match_count = 0
            
            # Find best matching segment in whisper words
            for i in range(len(whisper_word_segments)):
                match_count = 0
                for j, word in enumerate(chunk_words):
                    if i + j < len(whisper_word_segments):
                        whisper_word = whisper_word_segments[i + j]['word'].lower()
                        # Remove punctuation for matching
                        client_word_clean = re.sub(r'[^\w\']', '', word.lower())
                        whisper_word_clean = re.sub(r'[^\w\']', '', whisper_word)
                        
                        if client_word_clean == whisper_word_clean or client_word_clean in whisper_word_clean or whisper_word_clean in client_word_clean:
                            match_count += 1
                
                if match_count > best_match_count:
                    best_match_count = match_count
                    best_start_idx = i
                    best_end_idx = min(i + len(chunk_words), len(whisper_word_segments)) - 1
            
            if best_match_count > 0:
                chunk['start'] = whisper_word_segments[best_start_idx]['start']
                chunk['end'] = whisper_word_segments[best_end_idx]['end']
    
    # Final cleanup: ensure no chunk exceeds 100 chars (they shouldn't, but double-check)
    output = []
    for chunk in timed_chunks:
        # Verify the chunk text hasn't been modified
        if len(chunk['text']) > 100:
            # This shouldn't happen, but if it does, split it
            sub_chunks = split_into_chunks(chunk['text'], 100)
            sub_duration = (chunk['end'] - chunk['start']) / len(sub_chunks)
            
            for i, sub_text in enumerate(sub_chunks):
                output.append({
                    'start': round(chunk['start'] + (i * sub_duration), 3),
                    'end': round(chunk['start'] + ((i + 1) * sub_duration), 3),
                    'text': sub_text
                })
        else:
            output.append({
                'start': round(chunk['start'], 3),
                'end': round(chunk['end'], 3),
                'text': chunk['text']
            })
    
    # Debug: Print chunks to verify sizes
    print(f"\n📝 Generated {len(output)} chunks:")
    for i, chunk in enumerate(output[:10]):  # Show first 10 chunks
        print(f"  Chunk {i+1}: [{len(chunk['text'])} chars] - {chunk['text'][:50]}...")
    
    return output