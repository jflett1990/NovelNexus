import unittest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime

from memory.dynamic_memory import DynamicMemory
from agents.agent_prototype import AbstractAgent
from models.openai_client import get_openai_client

class TestAgent(AbstractAgent):
    """Test agent that inherits from AbstractAgent."""
    
    def __init__(self, project_id: str, memory: DynamicMemory, use_openai: bool = True):
        super().__init__(project_id, memory, use_openai, name="test_agent")
    
    def execute(self, test_param: str = "default_value"):
        """Implementation of the abstract method."""
        result = self.generate(f"Test prompt with {test_param}")
        
        # Store result in memory
        self.add_to_memory(
            json.dumps({"result": result.get("text")}),
            metadata={"type": "test_result", "param": test_param}
        )
        
        return {"status": "success", "output": result.get("text")}

class TestAbstractAgent(unittest.TestCase):
    """Test case for the AbstractAgent class and its features."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create mocks
        self.memory_mock = MagicMock(spec=DynamicMemory)
        self.openai_client_mock = MagicMock()
        
        # Create test agent
        self.agent = TestAgent("test_project", self.memory_mock, use_openai=True)
        
        # Mock the OpenAI client
        self.agent.openai_client = self.openai_client_mock
    
    @patch('agents.agent_prototype.get_openai_client')
    def test_initialization(self, mock_get_client):
        """Test agent initialization."""
        # Setup
        mock_get_client.return_value = self.openai_client_mock
        
        # Create a new agent to test initialization
        agent = TestAgent("test_project", self.memory_mock, use_openai=True)
        
        # Verify
        self.assertEqual(agent.name, "test_agent")
        self.assertEqual(agent.stage, "test")
        self.assertEqual(agent.project_id, "test_project")
        self.assertEqual(agent.memory, self.memory_mock)
        mock_get_client.assert_called_once()
    
    def test_execute(self):
        """Test the execute method implementation."""
        # Setup
        self.openai_client_mock.generate.return_value = {
            "text": "Generated response",
            "tokens": 10
        }
        
        # Execute
        result = self.agent.execute("test_value")
        
        # Verify
        self.openai_client_mock.generate.assert_called_once()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"], "Generated response")
        self.memory_mock.add_document.assert_called_once()
    
    def test_generate_method(self):
        """Test the generate method."""
        # Setup
        self.openai_client_mock.generate.return_value = {
            "text": "Generated response",
            "tokens": 10
        }
        
        # Execute
        result = self.agent.generate("Test prompt", system_prompt="System prompt", temperature=0.5)
        
        # Verify
        self.openai_client_mock.generate.assert_called_once_with(
            prompt="Test prompt",
            system_prompt="System prompt",
            model=None,  # This would be set by get_agent_model in real code
            temperature=0.5,
            json_mode=False,
            conversation_history=None,
            agent_name="test_agent"
        )
        self.assertEqual(result["text"], "Generated response")
    
    def test_generate_retry_logic(self):
        """Test that generate retries on failure."""
        # Setup - raise error on first call, succeed on second
        self.openai_client_mock.generate.side_effect = [
            Exception("API error"),
            {"text": "Success on retry", "tokens": 5}
        ]
        
        # Execute with reduced retry parameters for faster testing
        result = self.agent.generate("Test prompt", max_retries=2, retry_delay=0.1)
        
        # Verify
        self.assertEqual(self.openai_client_mock.generate.call_count, 2)
        self.assertEqual(result["text"], "Success on retry")
    
    def test_memory_interaction(self):
        """Test the memory interaction methods."""
        # Setup
        self.memory_mock.add_document.return_value = "doc123"
        self.memory_mock.query_memory.return_value = [{"text": "Result", "metadata": {}}]
        self.memory_mock.get_agent_memory.return_value = [{"text": "Doc1", "metadata": {}}, {"text": "Doc2", "metadata": {}}]
        
        # Test add_to_memory
        doc_id = self.agent.add_to_memory("Test content", {"key": "value"})
        self.assertEqual(doc_id, "doc123")
        self.memory_mock.add_document.assert_called_with(
            "Test content", 
            "test_agent", 
            {"key": "value", "agent": "test_agent", "timestamp": unittest.mock.ANY},
            None
        )
        
        # Test get_memory
        results = self.agent.get_memory("test query")
        self.memory_mock.query_memory.assert_called_with("test query", "test_agent", 5, 0.7)
        self.assertEqual(len(results), 1)
        
        # Test get_all_memory
        all_docs = self.agent.get_all_memory()
        self.memory_mock.get_agent_memory.assert_called_with("test_agent")
        self.assertEqual(len(all_docs), 2)
    
    def test_parse_json_response(self):
        """Test parsing JSON from LLM responses."""
        # Test direct JSON
        response = {"parsed_json": {"key": "value"}}
        result = self.agent.parse_json_response(response)
        self.assertEqual(result, {"key": "value"})
        
        # Test JSON string
        response = {"text": '{"key": "value"}'}
        result = self.agent.parse_json_response(response)
        self.assertEqual(result, {"key": "value"})
        
        # Test JSON in markdown
        response = {"text": "```json\n{\"key\": \"value\"}\n```"}
        result = self.agent.parse_json_response(response)
        self.assertEqual(result, {"key": "value"})
        
        # Test JSON extraction from text
        response = {"text": "Some text before {\"key\": \"value\"} and after"}
        result = self.agent.parse_json_response(response)
        self.assertEqual(result, {"key": "value"})
        
        # Test failed parsing
        response = {"text": "Not a JSON string"}
        result = self.agent.parse_json_response(response)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main() 