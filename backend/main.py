import re
from aligner import align_audio
from vttgen import generate_vtt


def clean_format(text: str) -> str:
    """Clean transcript by removing bullet points and formatting"""
    # Split into lines
    lines = text.splitlines()
    
    cleaned_lines = []
    
    for line in lines:
        # Remove leading/trailing whitespace
        line = line.strip()
        
        # Remove bullet characters at the start
        line = re.sub(r'^[•\-\*\u2022]+\s*', '', line)
        
        # Skip empty lines
        if line:
            cleaned_lines.append(line)
    
    # Join with single blank line between paragraphs
    return "\n\n".join(cleaned_lines)


def preprocess_transcript(raw_path, clean_path):
    """
    Read raw transcript, clean it, and save to clean_transcript.txt
    Returns the cleaned transcript.
    """
    # Read raw transcript
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
    
    # Clean the transcript
    cleaned_text = clean_format(raw_text)
    
    # Save cleaned version to clean_transcript.txt
    with open(clean_path, "w", encoding="utf-8") as f:
        f.write(cleaned_text)
    
    print("✅ Transcript cleaned and saved!")
    print(f"   Raw file: {raw_path}")
    print(f"   Cleaned file: {clean_path}")
    print(f"   Raw length: {len(raw_text)} chars")
    print(f"   Cleaned length: {len(cleaned_text)} chars")
    
    return cleaned_text


# Paths
raw_transcript_path = "inputs/transcript.txt"
clean_transcript_path = "inputs/clean_transcript.txt"
audio_path = "inputs/navigating.mp3"

# Pre-process: read raw, clean it, save to clean_transcript.txt
cleaned_transcript = preprocess_transcript(raw_transcript_path, clean_transcript_path)

# Now align using the cleaned transcript (reading from clean_transcript.txt is optional since we already have it)
segments = align_audio(audio_path, cleaned_transcript)

# Generate VTT
generate_vtt(segments, "outputs/output.vtt")

print(f"✅ Done! {len(segments)} captions generated.")