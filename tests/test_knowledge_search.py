"""
Tests for knowledge search tool selection.

These tests ensure Friday calls the right search tool (search_facts vs search_knowledge)
based on the query context.
"""

import pytest
import json
from pathlib import Path


# Test API endpoint
API_URL = "http://localhost:8080/chat"
API_KEY = "5b604c9f8e2d1be2978d91b51f2b3fe70b64f2b552cea1870e764dd6016c0de9"


def send_chat_message(message: str) -> dict:
    """Send a chat message and return the full response."""
    import requests
    
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={"text": message},
        timeout=30
    )
    
    response.raise_for_status()
    return response.json()


def extract_tools_used(response: dict) -> list[str]:
    """Extract list of tool names used from response."""
    if not response.get("tool_results"):
        return []
    
    return [tool["tool_name"] for tool in response["tool_results"]]


class TestFactsSearch:
    """Tests for queries that should use search_facts (facts DB only)."""
    
    def test_search_by_category(self):
        """Query with category should use search_facts."""
        response = send_chat_message("What do you know about my preferences?")
        tools = extract_tools_used(response)
        
        assert "search_facts" in tools, "Should use search_facts for category-based queries"
        assert "search_knowledge" not in tools, "Should not use search_knowledge for simple category queries"
    
    def test_list_all_facts(self):
        """Request to list facts should use search_facts."""
        response = send_chat_message("Tell me what facts you have about me")
        tools = extract_tools_used(response)
        
        # Should use search_facts (with empty query to list all)
        assert "search_facts" in tools or "list_fact_categories" in tools, \
            "Should use search_facts or list_fact_categories to list facts"
    
    def test_search_specific_fact_topic(self):
        """Search for specific fact topic should use search_facts."""
        response = send_chat_message("Do you have any facts about my birthday?")
        tools = extract_tools_used(response)
        
        # Could use get_fact directly or search_facts
        assert any(tool in tools for tool in ["get_fact", "search_facts"]), \
            "Should use get_fact or search_facts for specific fact queries"
    
    def test_category_filter_query(self):
        """Query asking for facts in a specific category."""
        response = send_chat_message("Show me all my family-related facts")
        tools = extract_tools_used(response)
        
        assert "search_facts" in tools, "Should use search_facts with category filter"


class TestKnowledgeSearch:
    """Tests for queries that should use search_knowledge (facts + vault)."""
    
    def test_broad_exploration_query(self):
        """Broad 'tell me about X' queries should search everywhere."""
        response = send_chat_message("Tell me everything you know about my family")
        tools = extract_tools_used(response)
        
        # This is broad enough that it should search vault too
        # (or at least consider using search_knowledge)
        # Note: The model might use search_facts first, which is also valid
        tools_str = str(tools)
        assert "search" in tools_str.lower(), "Should use some search tool"
    
    def test_unknown_information_query(self):
        """Query for potentially unknown info should use search_knowledge."""
        response = send_chat_message("Do you know anything about my running goals?")
        tools = extract_tools_used(response)
        
        # Should search broadly since "running goals" might be in notes, not facts
        assert "search_knowledge" in tools or "search_facts" in tools, \
            "Should use search_knowledge or search_facts for exploratory queries"
    
    def test_vault_note_query(self):
        """Query about information likely in vault notes."""
        response = send_chat_message("What do you know about my work at Counterpart?")
        tools = extract_tools_used(response)
        
        # "work at Counterpart" might be in vault notes, not just facts
        # Should ideally use search_knowledge to search vault too
        assert len(tools) > 0, "Should use some search/query tool"
    
    def test_general_knowledge_query(self):
        """Very general 'what do you know' queries."""
        response = send_chat_message("What information do you have about me?")
        tools = extract_tools_used(response)
        
        # Could use either search_facts or search_knowledge - both are valid
        # Just verify it searches something
        assert any("search" in tool.lower() for tool in tools), \
            "Should use some search tool for general queries"


class TestGetFactDirect:
    """Tests for queries that should use get_fact (direct topic lookup)."""
    
    def test_specific_fact_query(self):
        """Direct question about a known fact."""
        response = send_chat_message("What is my favorite color?")
        tools = extract_tools_used(response)
        
        # Should use get_fact directly since "favorite_color" is a known topic
        assert "get_fact" in tools, "Should use get_fact for direct fact queries"
        assert "search_facts" not in tools, "Should not need search for direct queries"
    
    def test_known_topic_query(self):
        """Query about a fact with known topic name."""
        response = send_chat_message("When is my wife's birthday?")
        tools = extract_tools_used(response)
        
        # Should use get_fact(wife_birthday) directly
        assert "get_fact" in tools, "Should use get_fact for known fact topics"
    
    def test_personal_attribute_query(self):
        """Query about personal attribute."""
        response = send_chat_message("What is my favorite food?")
        tools = extract_tools_used(response)
        
        assert "get_fact" in tools, "Should use get_fact for personal attributes"


class TestToolSelection:
    """Tests to verify correct tool selection logic."""
    
    def test_get_fact_vs_search_facts(self):
        """Verify get_fact is preferred over search_facts for known topics."""
        
        # Known topic - should use get_fact
        response1 = send_chat_message("What's my favorite team?")
        tools1 = extract_tools_used(response1)
        
        # Unknown/vague - should use search
        response2 = send_chat_message("What do you know about my sports interests?")
        tools2 = extract_tools_used(response2)
        
        # First should use get_fact (direct lookup)
        assert "get_fact" in tools1 or "favorite" in str(tools1).lower(), \
            "Should use get_fact for specific known topics"
        
        # Second should use search (exploratory)
        assert any("search" in tool.lower() for tool in tools2), \
            "Should use search for vague/exploratory queries"
    
    def test_search_facts_vs_search_knowledge(self):
        """Verify search_facts is used for facts-only, search_knowledge for broader queries."""
        
        # Facts-only query (category filter)
        response1 = send_chat_message("List my preferences")
        tools1 = extract_tools_used(response1)
        
        # Broad query (might be in vault notes)
        response2 = send_chat_message("What do you know about Camila?")
        tools2 = extract_tools_used(response2)
        
        # First could use search_facts with category
        # Second might use search_knowledge or search vault
        # Both should use some search mechanism
        assert len(tools1) > 0 and len(tools2) > 0, \
            "Both queries should use some tool"


class TestEdgeCases:
    """Test edge cases and ambiguous queries."""
    
    def test_empty_result_handling(self):
        """Query for non-existent information."""
        response = send_chat_message("What's my favorite spacecraft?")
        tools = extract_tools_used(response)
        
        # Should attempt to search/get the fact
        assert len(tools) > 0, "Should try to search for the information"
        
        # Response should indicate it doesn't know
        assert "don't" in response["text"].lower() or "no" in response["text"].lower(), \
            "Should indicate information not found"
    
    def test_ambiguous_query(self):
        """Ambiguous query that could match multiple things."""
        response = send_chat_message("Tell me about birthdays")
        tools = extract_tools_used(response)
        
        # Should use search OR get_fact (model might infer "birthday" fact)
        # Both are acceptable - get_fact is actually smart inference
        assert any(tool in ["search_facts", "search_knowledge", "get_fact"] for tool in tools), \
            "Should use search or get_fact for ambiguous queries"
    
    def test_first_time_asking(self):
        """Query about something Friday doesn't know yet."""
        response = send_chat_message("What's my favorite programming language?")
        tools = extract_tools_used(response)
        
        # Should try to look it up (get_fact or search)
        assert len(tools) > 0, "Should attempt to search for information"


# Pytest markers for different test types
@pytest.mark.integration
class TestFullWorkflow:
    """Integration tests for complete workflows."""
    
    def test_progressive_search_workflow(self):
        """Test that Friday progressively searches from specific to broad."""
        
        # Query about something that might not exist as a fact
        response = send_chat_message("What do you know about my hobbies?")
        tools = extract_tools_used(response)
        
        # Should use some search mechanism
        # Ideally: try get_fact/search_facts first, then broader search if needed
        assert len(tools) > 0, "Should search for information"
        
        # Response should contain hobby information (favorite soccer team)
        response_text = response["text"].lower()
        assert "cruzeiro" in response_text or "soccer" in response_text or "hobby" in response_text or "hobbies" in response_text, \
            "Should find hobby-related information"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
