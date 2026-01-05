"""
Friday 3.0 Media Tools

Tools for generating images and audio using npcpy.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent
from settings import settings

import logging
import os
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

# Media output directory
MEDIA_DIR = settings.PATHS["data"] / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


@agent.tool_plain
def generate_image(
    prompt: str,
    style: str = "realistic",
    size: str = "512x512"
) -> str:
    """Generate an image from a text prompt using Stable Diffusion on remote GPU server.
    
    This sends a request to a remote Stable Diffusion service running on a GPU server.
    The image will be saved to the data/media directory.
    
    Args:
        prompt: Text description of the image to generate
        style: Style of image (realistic, artistic, cartoon, etc.)
        size: Image size as WIDTHxHEIGHT (e.g., "512x512", "768x768")
    
    Returns:
        str: Path to the generated image file, or error message
    
    Examples:
        generate_image("a serene mountain landscape at sunset")
        generate_image("a cute robot reading a book", style="cartoon")
    """
    # Get Stable Diffusion service URL from settings
    sd_service_url = settings.STABLE_DIFFUSION_URL
    
    if not sd_service_url:
        logger.warning("[MEDIA] STABLE_DIFFUSION_URL not configured")
        return "Image generation not available - STABLE_DIFFUSION_URL not set in environment"
    
    try:
        import httpx
        import base64
        from datetime import datetime
        
        # Parse size
        try:
            width, height = map(int, size.lower().split('x'))
        except:
            width, height = 512, 512
        
        # Enhance prompt with style
        enhanced_prompt = f"{prompt}, {style} style" if style != "realistic" else prompt
        
        logger.info(f"[MEDIA] Requesting image generation from {sd_service_url}: {enhanced_prompt[:100]}")
        
        # docker-diffusers-api format (kiri-art)
        payload = {
            "modelInputs": {
                "prompt": enhanced_prompt,
                "num_inference_steps": 25,  # DPMSolver is fast, only needs 20-25 steps
                "guidance_scale": 7.5,
                "width": width,
                "height": height,
            },
            "callInputs": {
                "MODEL_ID": "runwayml/stable-diffusion-v1-5",  # Required
                "PIPELINE": "StableDiffusionPipeline",
                "SCHEDULER": "DPMSolverMultistepScheduler",  # Fast scheduler
                "safety_checker": False,
            }
        }
        
        # Send request to Stable Diffusion service
        # Note: First generation after model load can take 2-3 minutes
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                sd_service_url,  # POST to root endpoint
                json=payload
            )
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Extract base64 image from response
            if "image_base64" in result:
                image_data = base64.b64decode(result["image_base64"])
            elif "images" in result and len(result["images"]) > 0:
                image_data = base64.b64decode(result["images"][0])
            else:
                logger.error(f"[MEDIA] Unexpected response format: {result.keys()}")
                return "Image generation failed: unexpected response format"
            
            # Save the image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.png"
            filepath = MEDIA_DIR / filename
            
            with open(filepath, "wb") as f:
                f.write(image_data)
            
            if filepath.exists():
                logger.info(f"[MEDIA] Image saved to: {filepath}")
                # Return special format that Telegram bot can detect
                return f"[IMAGE:{filepath}]\nImage generated: {prompt}"
            else:
                logger.warning("[MEDIA] Image generation returned but file not found")
                return "Image generation completed but file could not be saved"
    
    except httpx.ConnectError:
        logger.error(f"[MEDIA] Cannot connect to Stable Diffusion service at {sd_service_url}")
        return f"Image generation service unavailable at {sd_service_url}"
    except httpx.TimeoutException:
        logger.error("[MEDIA] Stable Diffusion service timeout")
        return "Image generation timed out (exceeded 120 seconds)"
    except httpx.HTTPStatusError as e:
        logger.error(f"[MEDIA] Stable Diffusion service error: {e.response.status_code}")
        return f"Image generation failed: HTTP {e.response.status_code}"
    except Exception as e:
        logger.error(f"[MEDIA] Image generation failed: {e}")
        return f"Failed to generate image: {str(e)}"


@agent.tool_plain
def generate_speech(
    text: str,
    lang: str = "en"
) -> str:
    """Convert text to speech audio using LOCAL TTS (gTTS).
    
    This uses local text-to-speech without any external API calls.
    The audio will be saved to the data/media directory.
    
    IMPORTANT: This tool returns a special [AUDIO:path] marker. You MUST include
    this marker EXACTLY as returned in your final response to the user so the 
    audio file can be sent. Example: "[AUDIO:/path/to/file.mp3]\nHello there!"
    
    Supported languages:
    - en: English (default)
    - pt: Portuguese (Brazilian)
    
    Args:
        text: Text to convert to speech
        lang: Language code - "en" for English or "pt" for Portuguese
    
    Returns:
        str: Response containing [AUDIO:path] marker and text transcript
    
    Examples:
        generate_speech("Hello, this is a test")
        generate_speech("Olá, como vai?", lang="pt")
    """
    try:
        from gtts import gTTS
        from datetime import datetime
        import re
        
        # AUTO-DETECT language if not explicitly set
        # Check for Portuguese characters/patterns
        if lang == "en":
            # Portuguese indicators: ã, õ, ç, common Portuguese words
            pt_indicators = [
                r'[ãõç]',  # Portuguese special characters
                r'\b(olá|bom dia|boa tarde|boa noite|obrigad[oa]|por favor|como vai|tudo bem|você|está)\b'
            ]
            if any(re.search(pattern, text.lower()) for pattern in pt_indicators):
                lang = "pt"
                logger.info(f"[MEDIA] Auto-detected Portuguese text, switching lang to 'pt'")
        
        logger.info(f"[MEDIA] Generating speech with gTTS (lang={lang}): {text[:100]}")
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"speech_{timestamp}.mp3"
        filepath = MEDIA_DIR / filename
        
        # Generate speech using gTTS (Google Text-to-Speech, no API key needed)
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(str(filepath))
        
        if filepath.exists():
            logger.info(f"[MEDIA] Audio saved to: {filepath}")
            # Return special format that Telegram bot can detect
            return f"[AUDIO:{filepath}]\nSpeech generated: {text[:100]}"
        else:
            logger.warning("[MEDIA] Speech generation returned but file not found")
            return "Speech generation completed but file could not be saved"
            
    except ImportError as e:
        logger.error(f"[MEDIA] Missing dependencies: {e}")
        return "Speech generation not available - gTTS not installed. Run: pipenv install gtts"
    except Exception as e:
        logger.error(f"[MEDIA] Speech generation failed: {e}")
        return f"Failed to generate speech: {str(e)}"


def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe audio to text using Whisper ASR service.
    
    This is NOT a tool - it's a utility function used by the Telegram bot
    to convert voice messages to text before sending to the agent.
    
    Args:
        audio_file_path: Path to audio file (local path or URL)
    
    Returns:
        Transcribed text or error message
    """
    try:
        import httpx
        from pathlib import Path
        
        whisper_url = settings.WHISPER_SERVICE_URL
        
        if not whisper_url:
            logger.error("[MEDIA] WHISPER_SERVICE_URL not configured")
            return "[Error: Speech-to-text service not configured]"
        
        logger.info(f"[MEDIA] Transcribing audio with Whisper: {audio_file_path}")
        
        # Check if file exists locally
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            logger.error(f"[MEDIA] Audio file not found: {audio_path}")
            return f"[Error: Audio file not found]"
        
        # Send to Whisper service
        with httpx.Client(timeout=60) as client:
            with open(audio_path, 'rb') as audio_file:
                files = {'audio_file': (audio_path.name, audio_file, 'audio/ogg')}
                response = client.post(
                    f"{whisper_url}/asr",
                    files=files,
                    params={'task': 'transcribe', 'output': 'txt'}
                )
                
                if response.status_code == 200:
                    transcribed_text = response.text.strip()
                    logger.info(f"[MEDIA] Transcription successful: {transcribed_text[:100]}")
                    return transcribed_text
                else:
                    logger.error(f"[MEDIA] Whisper API error: {response.status_code} - {response.text}")
                    return f"[Error: Transcription failed - {response.status_code}]"
                    
    except Exception as e:
        logger.error(f"[MEDIA] Transcription failed: {e}")
        return f"[Error: Failed to transcribe audio - {str(e)}]"
