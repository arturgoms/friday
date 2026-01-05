"""
Tests for web tools (search and fetch).

These tests mock httpx to avoid real network calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


def test_web_search_success():
    """Test successful web search."""
    # Mock the httpx.Client to avoid real network calls
    mock_response = Mock()
    mock_response.json.return_value = {
        'results': [
            {
                'title': 'Test Result 1',
                'url': 'https://example.com/1',
                'content': 'This is test content 1'
            },
            {
                'title': 'Test Result 2',
                'url': 'https://example.com/2',
                'content': 'This is test content 2'
            }
        ]
    }
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        # Import here to avoid agent decorator issues
        from src.tools.web import web_search
        
        result = web_search("test query", num_results=2)
        
        assert "Test Result 1" in result
        assert "Test Result 2" in result
        assert "https://example.com/1" in result
        assert "test query" in result


def test_web_search_no_results():
    """Test web search with no results."""
    mock_response = Mock()
    mock_response.json.return_value = {'results': []}
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.web import web_search
        
        result = web_search("nonexistent query")
        
        assert "No results found" in result


def test_web_search_timeout():
    """Test web search timeout handling."""
    import httpx
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("Timeout")
        
        from src.tools.web import web_search
        
        result = web_search("test query")
        
        assert "timed out" in result.lower()


def test_web_search_limits_results():
    """Test that num_results is clamped to max 10."""
    mock_response = Mock()
    mock_response.json.return_value = {
        'results': [{'title': f'Result {i}', 'url': f'http://ex.com/{i}', 'content': ''} 
                   for i in range(20)]
    }
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.web import web_search
        
        result = web_search("test", num_results=100)  # Request 100 but should cap at 10
        
        # Should only show 10 results
        assert result.count("http://ex.com/") == 10


def test_web_fetch_success():
    """Test successful web page fetch."""
    mock_response = Mock()
    mock_response.text = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Test Heading</h1>
                <p>This is test content.</p>
                <script>console.log('remove me');</script>
            </body>
        </html>
    """
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.web import web_fetch
        
        result = web_fetch("https://example.com")
        
        assert "Test Heading" in result
        assert "test content" in result
        assert "console.log" not in result  # Script should be removed
        assert "https://example.com" in result


def test_web_fetch_truncates_long_content():
    """Test that long content is truncated."""
    mock_response = Mock()
    mock_response.text = f"<html><body><p>{'A' * 10000}</p></body></html>"
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.web import web_fetch
        
        result = web_fetch("https://example.com", max_length=1000)
        
        assert "[Content truncated...]" in result
        assert len(result) < 1200  # Should be close to max_length


def test_web_fetch_non_html_content():
    """Test fetching non-HTML content."""
    mock_response = Mock()
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.web import web_fetch
        
        result = web_fetch("https://example.com/doc.pdf")
        
        assert "Cannot extract text" in result


def test_web_news():
    """Test web news search (should call web_search with news category)."""
    mock_response = Mock()
    mock_response.json.return_value = {
        'results': [
            {'title': 'News Article', 'url': 'https://news.com/1', 'content': 'News content'}
        ]
    }
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.web import web_news
        
        result = web_news("breaking news", num_results=5)
        
        assert "News Article" in result
        
        # Verify it called with news category
        call_args = mock_client.return_value.__enter__.return_value.get.call_args
        assert 'categories=news' in str(call_args)


def test_html_to_text_removes_scripts_and_styles():
    """Test that HTML to text converter removes scripts and styles."""
    from src.tools.web import _html_to_text
    
    html = """
        <html>
            <head>
                <style>body { color: red; }</style>
            </head>
            <body>
                <p>Visible content</p>
                <script>alert('hidden');</script>
                <p>More content</p>
            </body>
        </html>
    """
    
    result = _html_to_text(html)
    
    assert "Visible content" in result
    assert "More content" in result
    assert "alert" not in result
    assert "color: red" not in result


def test_html_to_text_decodes_entities():
    """Test HTML entity decoding."""
    from src.tools.web import _html_to_text
    
    html = "<p>Test &amp; example &lt;tag&gt; &quot;quote&quot;</p>"
    
    result = _html_to_text(html)
    
    assert "&" in result
    assert "<tag>" in result
    assert '"quote"' in result
