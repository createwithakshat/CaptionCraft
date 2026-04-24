import subprocess
from pydub import AudioSegment, silence


def normalize_audio(input_path, output_path="normalized.wav"):
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        "-vn",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def detect_silences(audio_path):
    audio = AudioSegment.from_wav(audio_path)
    
    silences = silence.detect_silence(
        audio,
        min_silence_len=200,   # ms
        silence_thresh=audio.dBFS - 16
    )
    
    return [(start / 1000, end / 1000) for start, end in silences]