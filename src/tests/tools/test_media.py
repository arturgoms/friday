"""
Tests for Friday Media Tools

Tests media generation tools for images and speech.

Tools tested:
- generate_image() - Generate images using Stable Diffusion
- generate_speech() - Convert text to speech using gTTS
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.media import (
    generate_image,
    generate_speech,
)


# =============================================================================
# Helper Functions
# =============================================================================

def check_for_none_values(data, path=''):
    """Recursively check for None values in nested data structures.
    
    Returns list of paths where None values were found.
    Note: This is for dict/list structures, not strings.
    """
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path))
    
    return none_found


# =============================================================================
# Image Generation Tests
# =============================================================================

def test_generate_image_returns_str():
    """Test image generation returns a string."""
    with patch('src.tools.media.settings') as mock_settings:
        mock_settings.STABLE_DIFFUSION_URL = None
        
        result = generate_image("test prompt")
        assert isinstance(result, str)
        assert result is not None


def test_generate_image_no_service_url():
    """Test image generation when service URL not configured."""
    with patch('src.tools.media.settings') as mock_settings:
        mock_settings.STABLE_DIFFUSION_URL = None
        
        result = generate_image("a beautiful landscape")
        
        assert isinstance(result, str)
        assert "not available" in result.lower() or "not set" in result.lower()


def test_generate_image_success():
    """Test successful image generation."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"image_base64": "aGVsbG8="}  # base64 encoded "hello"
        mock_response.raise_for_status = Mock()
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        
        result = generate_image("a cute robot", style="cartoon", size="512x512")
        
        assert isinstance(result, str)
        # Should contain special marker
        assert "[IMAGE:" in result
        # Should contain success indicator
        assert "generated" in result.lower() or "Image" in result


def test_generate_image_connection_error():
    """Test image generation with connection error."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        import httpx
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.side_effect = httpx.ConnectError("Connection failed")
        
        result = generate_image("test prompt")
        
        assert isinstance(result, str)
        assert "unavailable" in result.lower() or "connect" in result.lower()


def test_generate_image_timeout():
    """Test image generation with timeout."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        import httpx
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.side_effect = httpx.TimeoutException("Request timed out")
        
        result = generate_image("test prompt")
        
        assert isinstance(result, str)
        assert "timeout" in result.lower() or "timed out" in result.lower()


def test_generate_image_http_error():
    """Test image generation with HTTP error."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        import httpx
        mock_response = Mock()
        mock_response.status_code = 500
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )
        
        result = generate_image("test prompt")
        
        assert isinstance(result, str)
        assert "failed" in result.lower() or "error" in result.lower()


def test_generate_image_invalid_size():
    """Test image generation with invalid size format."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"image_base64": "aGVsbG8="}
        mock_response.raise_for_status = Mock()
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        
        # Should handle invalid size gracefully and use default
        result = generate_image("test", size="invalid")
        
        assert isinstance(result, str)
        # Should still succeed (falls back to default size)


def test_generate_image_with_style():
    """Test image generation with different styles."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"image_base64": "aGVsbG8="}
        mock_response.raise_for_status = Mock()
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        
        # Test with different styles
        for style in ["realistic", "cartoon", "artistic"]:
            result = generate_image("test prompt", style=style)
            assert isinstance(result, str)


# =============================================================================
# Speech Generation Tests
# =============================================================================

def test_generate_speech_returns_str():
    """Test speech generation returns a string."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        result = generate_speech("Hello world")
        assert isinstance(result, str)
        assert result is not None


def test_generate_speech_success_english():
    """Test successful speech generation in English."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        result = generate_speech("Hello, this is a test", lang="en")
        
        assert isinstance(result, str)
        # Should contain special marker
        assert "[AUDIO:" in result
        # Should contain success indicator
        assert "generated" in result.lower() or "Speech" in result


def test_generate_speech_success_portuguese():
    """Test successful speech generation in Portuguese."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        result = generate_speech("Olá, como vai?", lang="pt")
        
        assert isinstance(result, str)
        assert "[AUDIO:" in result


def test_generate_speech_auto_detect_portuguese():
    """Test speech generation auto-detects Portuguese."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        # Portuguese text with special characters
        result = generate_speech("Olá, tudo bem? Obrigado!", lang="en")
        
        # Should still succeed (auto-detection happens internally)
        assert isinstance(result, str)
        assert "[AUDIO:" in result


def test_generate_speech_missing_dependency():
    """Test speech generation with missing gTTS dependency."""
    with patch('gtts.gTTS', side_effect=ImportError("gTTS not found")):
        
        result = generate_speech("test")
        
        assert isinstance(result, str)
        assert "not available" in result.lower() or "not installed" in result.lower()


def test_generate_speech_file_save_error():
    """Test speech generation when file save fails."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=False):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        result = generate_speech("test")
        
        assert isinstance(result, str)
        assert "could not be saved" in result.lower() or "completed" in result.lower()


def test_generate_speech_exception():
    """Test speech generation with unexpected exception."""
    with patch('gtts.gTTS') as mock_gtts:
        
        mock_gtts.side_effect = Exception("Unexpected error")
        
        result = generate_speech("test")
        
        assert isinstance(result, str)
        assert "failed" in result.lower() or "error" in result.lower()


def test_generate_speech_long_text():
    """Test speech generation with long text."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        # Long text (over 100 characters)
        long_text = "This is a very long text " * 10
        result = generate_speech(long_text)
        
        assert isinstance(result, str)
        assert "[AUDIO:" in result
        # Should show truncated text in response
        assert len(result) < len(long_text) + 100  # Truncated version


# =============================================================================
# None Value Detection Tests
# =============================================================================

def test_generate_image_not_none():
    """CRITICAL: Ensure image generation doesn't return None."""
    with patch('src.tools.media.settings') as mock_settings:
        mock_settings.STABLE_DIFFUSION_URL = None
        
        result = generate_image("test")
        
        assert result is not None
        assert isinstance(result, str)


def test_generate_speech_not_none():
    """CRITICAL: Ensure speech generation doesn't return None."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        result = generate_speech("test")
        
        assert result is not None
        assert isinstance(result, str)


def test_all_media_tools_not_none():
    """CRITICAL: Batch test - check all media tools don't return None."""
    errors = []
    
    # Test generate_image
    with patch('src.tools.media.settings') as mock_settings:
        mock_settings.STABLE_DIFFUSION_URL = None
        result = generate_image("test")
        if result is None:
            errors.append("generate_image returned None")
    
    # Test generate_speech
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        result = generate_speech("test")
        if result is None:
            errors.append("generate_speech returned None")
    
    # Assert no errors found
    assert len(errors) == 0, \
        f"CRITICAL: Found None values in media tools:\n" + "\n".join(errors)


# =============================================================================
# Response Format Tests
# =============================================================================

def test_generate_image_response_format():
    """Test image generation response contains required markers."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"image_base64": "aGVsbG8="}
        mock_response.raise_for_status = Mock()
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        
        result = generate_image("test")
        
        # Should contain IMAGE marker for Telegram bot
        assert "[IMAGE:" in result
        assert "]" in result


def test_generate_speech_response_format():
    """Test speech generation response contains required markers."""
    with patch('gtts.gTTS') as mock_gtts, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_tts_instance = Mock()
        mock_gtts.return_value = mock_tts_instance
        
        result = generate_speech("test")
        
        # Should contain AUDIO marker for Telegram bot
        assert "[AUDIO:" in result
        assert "]" in result


def test_generate_image_alternate_response_format():
    """Test image generation with alternate API response format."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.exists', return_value=True):
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        # Test with "images" array format
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"images": ["aGVsbG8="]}
        mock_response.raise_for_status = Mock()
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        
        result = generate_image("test")
        
        assert isinstance(result, str)
        assert "[IMAGE:" in result


def test_generate_image_unexpected_response_format():
    """Test image generation with unexpected API response format."""
    with patch('src.tools.media.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.STABLE_DIFFUSION_URL = "http://localhost:8000"
        
        # Unexpected format (no image data)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}  # No image data
        mock_response.raise_for_status = Mock()
        
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.post.return_value = mock_response
        
        result = generate_image("test")
        
        assert isinstance(result, str)
        assert "failed" in result.lower() or "unexpected" in result.lower()
