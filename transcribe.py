import os
import json
from datetime import datetime
from pathlib import Path
import yt_dlp
import httpx
from pydub import AudioSegment
from deepgram import DeepgramClient, PrerecordedOptions
from dotenv import load_dotenv
import tempfile

def get_download_path() -> Path:
    """Get the path to store downloaded audio files."""
    download_dir = Path("downloaded_audio")
    download_dir.mkdir(exist_ok=True)
    return download_dir

def get_transcript_path() -> Path:
    """Get the path to store transcripts."""
    transcript_dir = Path("transcripts")
    transcript_dir.mkdir(exist_ok=True)
    return transcript_dir

def get_existing_transcript(video_id: str) -> dict | None:
    """Check if a transcript already exists for the video."""
    transcript_dir = get_transcript_path()
    transcript_path = transcript_dir / f"{video_id}.json"
    
    if transcript_path.exists():
        print(f"Using existing transcript: {transcript_path}")
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def download_youtube_audio(url: str) -> tuple[str, str]:
    """Download audio from YouTube video in an efficient format."""
    # Create a filename from the YouTube ID
    video_id = url.split("v=")[1].split("&")[0]
    download_dir = get_download_path()
    output_path = download_dir / f"{video_id}.mp3"
    
    # Check if file already exists
    if output_path.exists():
        print(f"Using existing audio file: {output_path}")
        return str(output_path), video_id
    
    ydl_opts = {
        'format': 'bestaudio/best',  # Get best audio quality
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',  # Standard MP3 format
            'preferredquality': '64',  # Lower bitrate, still good for speech
        }],
        'outtmpl': str(output_path)[:-4],  # Remove .mp3 as it will be added by postprocessor
    }
    
    print(f"Downloading audio to: {output_path}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return str(output_path), info.get('title', video_id)

def transcribe_audio_chunk(chunk: AudioSegment, deepgram_client) -> str:
    """Transcribe a single audio chunk using Deepgram."""
    # Export chunk to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=True) as temp_file:
        chunk.export(temp_file.name, format='mp3')
        
        with open(temp_file.name, 'rb') as audio:
            source = {'buffer': audio.read(), 'mimetype': 'audio/mp3'}
            
            options = PrerecordedOptions(
                model="nova-2",
                language="en",
                smart_format=True,
                paragraphs=True,
                diarize=True,
            )
            
            # Set timeout to 1 minute for chunks
            timeout = httpx.Timeout(60.0, connect=10.0)
            response = deepgram_client.listen.rest.v("1").transcribe_file(source, options, timeout=timeout)
            return response.results.channels[0].alternatives[0].transcript

def transcribe_audio_file(file_path: str, deepgram_client, chunk_size_ms: int = 5 * 60 * 1000) -> str:
    """Transcribe an audio file using Deepgram by processing it in chunks."""
    print("Loading audio file...")
    audio = AudioSegment.from_mp3(file_path)
    
    # Split audio into chunks
    chunks = []
    for i in range(0, len(audio), chunk_size_ms):
        chunks.append(audio[i:i + chunk_size_ms])
    
    print(f"Processing {len(chunks)} chunks...")
    transcripts = []
    
    # Process each chunk
    for i, chunk in enumerate(chunks, 1):
        print(f"Transcribing chunk {i}/{len(chunks)}...")
        try:
            transcript = transcribe_audio_chunk(chunk, deepgram_client)
            transcripts.append(transcript)
        except Exception as e:
            print(f"Error processing chunk {i}: {e}")
            transcripts.append("[Error transcribing this segment]")
    
    # Combine all transcripts
    return " ".join(transcripts)

def save_transcript(text: str, video_id: str, video_title: str) -> str:
    """Save the transcript to a JSON file with metadata."""
    transcript_dir = get_transcript_path()
    filename = f"{video_id}.json"
    
    data = {
        "video_id": video_id,
        "video_title": video_title,
        "transcript": text
    }
    
    output_path = transcript_dir / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nTranscript saved to: {output_path}")
    return str(output_path)

def main():
    try:
        # Load environment variables
        load_dotenv()
        deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        if not deepgram_api_key:
            raise ValueError("DEEPGRAM_API_KEY not found in environment variables")

        # Initialize Deepgram client
        deepgram = DeepgramClient(deepgram_api_key)

        # YouTube URL to transcribe
        youtube_url = "https://www.youtube.com/watch?v=OHWnPOKh_S0&pp=ygULbGV4IGZyaWRtYW4%3D"
        
        # Get video ID from URL
        video_id = youtube_url.split("v=")[1].split("&")[0]
        
        # Check for existing transcript
        existing_transcript = get_existing_transcript(video_id)
        if existing_transcript:
            print("\nTranscript:")
            print("-----------")
            print(existing_transcript["transcript"])
            return
        
        # Download audio and get video title
        audio_path, video_title = download_youtube_audio(youtube_url)
        
        print(f"Transcribing audio...")
        # Process in 5-minute chunks
        transcript = transcribe_audio_file(audio_path, deepgram, chunk_size_ms=5 * 60 * 1000)
        
        # Save transcript
        save_transcript(transcript, video_id, video_title)
        
        print("\nTranscript:")
        print("-----------")
        print(transcript)

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()