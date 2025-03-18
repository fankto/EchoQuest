import asyncio
import json
import os
import sys
from loguru import logger

import httpx
from pydub import AudioSegment

# Add the current directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.config import settings

async def test_assembly_api(audio_file_path):
    """Test the AssemblyAI API with a given audio file"""
    
    # Configuration
    assembly_api_key = settings.ASSEMBLY_API_KEY
    assembly_base_url = "https://api.assemblyai.com/v2"
    
    logger.info(f"Testing AssemblyAI API with file: {audio_file_path}")
    logger.info(f"Using API key: {assembly_api_key[:5]}...{assembly_api_key[-5:]}")
    
    # Step 1: Upload the audio file
    logger.info("Step 1: Uploading audio file")
    
    with open(audio_file_path, "rb") as audio_file:
        data = audio_file.read()
    
    headers = {
        "authorization": assembly_api_key
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info(f"Starting upload (size: {len(data)} bytes)")
            
            response = await client.post(
                f"{assembly_base_url}/upload",
                headers=headers,
                content=data
            )
            
            if response.status_code != 200:
                logger.error(f"Upload failed: {response.status_code} - {response.text}")
                return
                
            upload_url = response.json().get("upload_url")
            logger.info(f"Upload successful: {upload_url}")
            
            # Step 2: Create transcription job
            logger.info("Step 2: Creating transcription job")
            
            # Configuration for transcription
            transcription_config = {
                "audio_url": upload_url,
                "speaker_labels": True,        # Enable speaker diarization
                "punctuate": True,             # Add punctuation
                "format_text": True,           # Clean up text (e.g., capitalization)
                "word_boost": ["interview", "question", "answer"],  # Boost relevant words
            }
            
            # Optionally add speakers_expected - usually better to let AssemblyAI detect automatically
            # transcription_config["speakers_expected"] = 2  # Only set if you know the exact number
            
            logger.info(f"Transcription config: {json.dumps(transcription_config)}")
            
            response = await client.post(
                f"{assembly_base_url}/transcript",
                json=transcription_config,
                headers={
                    "authorization": assembly_api_key,
                    "content-type": "application/json"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Transcription job creation failed: {response.status_code} - {response.text}")
                return
                
            transcript_id = response.json().get("id")
            logger.info(f"Transcription job created: {transcript_id}")
            
            # Step 3: Poll for completion
            logger.info("Step 3: Polling for completion")
            
            max_retries = 30
            retry_count = 0
            
            while retry_count < max_retries:
                response = await client.get(
                    f"{assembly_base_url}/transcript/{transcript_id}",
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"Polling failed: {response.status_code} - {response.text}")
                    return
                    
                result = response.json()
                status = result.get("status")
                
                logger.info(f"Polling status: {status} (attempt {retry_count+1}/{max_retries})")
                
                if status == "completed":
                    # Output the complete result
                    logger.info("Transcription completed!")
                    logger.info(f"Full response: {json.dumps(result, indent=2)}")
                    
                    # Print the text
                    logger.info(f"Transcript text: {result.get('text')}")
                    
                    # Print the utterances
                    if "utterances" in result:
                        logger.info(f"Found {len(result['utterances'])} utterances:")
                        for i, utterance in enumerate(result["utterances"]):
                            logger.info(f"Utterance {i+1} - Speaker {utterance['speaker']}: {utterance['text']}")
                    else:
                        logger.warning("No utterances found in response!")
                    
                    break
                elif status == "error":
                    logger.error(f"Transcription failed: {result.get('error')}")
                    return
                
                # Wait before polling again
                retry_count += 1
                await asyncio.sleep(10)
                
            else:
                logger.error("Transcription timed out!")
    
    except Exception as e:
        logger.error(f"Error in test: {e}")

if __name__ == "__main__":
    # Get the file path from args or use a default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Use most recent processed file
        processed_dir = settings.PROCESSED_DIR
        files = [f for f in os.listdir(processed_dir) if f.startswith("processed_") and f.endswith(".wav")]
        if not files:
            logger.error(f"No processed files found in {processed_dir}")
            sys.exit(1)
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: os.path.getmtime(os.path.join(processed_dir, x)), reverse=True)
        file_path = os.path.join(processed_dir, files[0])
    
    logger.info(f"Using file: {file_path}")
    
    # Run the test
    asyncio.run(test_assembly_api(file_path)) 