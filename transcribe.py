import os
from pathlib import Path
import yt_dlp
from deepgram import DeepgramClient, PrerecordedOptions
from dotenv import load_dotenv

def get_download_path() -> Path:
    """Get the path to store downloaded audio files."""
    download_dir = Path("downloaded_audio")
    download_dir.mkdir(exist_ok=True)
    return download_dir

def download_youtube_audio(url: str) -> str:
    """Download audio from YouTube video in an efficient format."""
    # Create a filename from the YouTube ID
    video_id = url.split("v=")[1].split("&")[0]
    download_dir = get_download_path()
    output_path = download_dir / f"{video_id}.mp3"
    
    # Check if file already exists
    if output_path.exists():
        print(f"Using existing audio file: {output_path}")
        return str(output_path)
    
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
        ydl.download([url])
        
    return str(output_path)

def transcribe_audio_file(file_path: str, deepgram_client) -> str:
    """Transcribe an audio file using Deepgram."""
    with open(file_path, 'rb') as audio:
        source = {'buffer': audio.read(), 'mimetype': 'audio/mp3'}
        
        options = PrerecordedOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            paragraphs=True,
            diarize=True,
        )
        
        response = deepgram_client.listen.rest.v("1").transcribe_file(source, options)
        return response.results.channels[0].alternatives[0].transcript

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
        
        audio_path = download_youtube_audio(youtube_url)
        
        print(f"Transcribing audio...")
        transcript = transcribe_audio_file(audio_path, deepgram)
        
        print("\nTranscript:")
        print("-----------")
        print(transcript)

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()