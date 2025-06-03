import json
import re
import time
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, List, Union

logger = logging.getLogger(__name__)

# Type variable for generic function
T = TypeVar('T')

# Regular expressions for robust JSON extraction
JSON_PATTERN = r'(\{[\s\S]*\})' 
JSON_ARRAY_PATTERN = r'(\[[\s\S]*\])'

def parse_json_safely(
    text: Union[str, Dict[str, Any]], 
    default_value: Any = None,
    expected_format: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Safely parse JSON from text with fallback to default value.
    
    Args:
        text: Text string to parse or already parsed dictionary
        default_value: Value to return if parsing fails
        expected_format: Optional expected format to validate against
        
    Returns:
        Parsed JSON data or default value if parsing fails
    """
    # If already a dict, just return it
    if isinstance(text, dict):
        return text
    
    # Default value if none provided
    if default_value is None:
        default_value = {}
    
    try:
        # Try parsing directly first
        try:
            result = json.loads(text)
            logger.debug("Successfully parsed JSON directly")
            return result
        except (json.JSONDecodeError, TypeError):
            # Fall back to robust parsing
            result = robust_json_parse(str(text))
            if result:
                logger.debug("Successfully parsed JSON with robust parsing")
                return result
            else:
                logger.warning(f"Failed to parse JSON, using default value")
                return default_value
    except Exception as e:
        logger.warning(f"Unexpected error parsing JSON: {str(e)}")
        return default_value

def sanitize_json(json_str: str) -> str:
    """Clean up common JSON issues to improve parsing success."""
    # Remove trailing commas before closing brackets
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Handle unquoted property names
    json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
    
    # Fix nested quotes
    json_str = re.sub(r'\\+"', '"', json_str)
    
    # Replace any "\n" literal strings with actual new lines
    json_str = json_str.replace('\\n', ' ')
    
    return json_str

def robust_json_parse(text: str) -> Dict[str, Any]:
    """Try multiple approaches to extract and parse JSON from text."""
    # Try to parse directly first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON object
    json_match = re.search(JSON_PATTERN, text)
    if json_match:
        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try with sanitization
            try:
                return json.loads(sanitize_json(json_str))
            except json.JSONDecodeError:
                pass
    
    # Look for JSON array pattern
    json_array_match = re.search(JSON_ARRAY_PATTERN, text)
    if json_array_match:
        json_str = json_array_match.group(1)
        try:
            array_data = json.loads(json_str)
            # Convert array to object if necessary
            if isinstance(array_data, list):
                return {"items": array_data}
            return array_data
        except json.JSONDecodeError:
            # Try with sanitization
            try:
                array_data = json.loads(sanitize_json(json_str))
                if isinstance(array_data, list):
                    return {"items": array_data}
                return array_data
            except json.JSONDecodeError:
                pass
    
    # Last resort: look for any JSON-like content
    # Extract anything between { } with the most balanced brackets
    stack = []
    potential_json = ""
    best_json = ""
    for i, char in enumerate(text):
        if char == '{':
            if not stack:
                potential_json = "{"
            else:
                potential_json += char
            stack.append('{')
        elif char == '}' and stack:
            stack.pop()
            potential_json += '}'
            if not stack and len(potential_json) > len(best_json):
                best_json = potential_json
        elif stack:
            potential_json += char
    
    if best_json:
        try:
            return json.loads(best_json)
        except json.JSONDecodeError:
            try:
                return json.loads(sanitize_json(best_json))
            except json.JSONDecodeError:
                pass
    
    # If all else fails, return a minimal valid structure
    logger.warning(f"Could not parse any valid JSON from text, returning minimal fallback")
    return {}

def validate_schema(data: Dict[str, Any], required_fields: List[str], schema_name: str) -> bool:
    """Validate that data contains all required fields."""
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        logger.warning(f"Schema validation failed for {schema_name}. Missing fields: {', '.join(missing_fields)}")
        return False
    
    return True

def with_retries(func: Callable[[], T], retries: int = 3, backoff: bool = True) -> T:
    """Execute a function with retries and exponential backoff."""
    last_exception = None
    
    for attempt in range(retries):
        try:
            result = func()
            
            # Return successfully if no exception
            return result
        except Exception as e:
            last_exception = e
            logger.warning(f"Attempt {attempt+1}/{retries} failed: {str(e)}")
            
            # Sleep with exponential backoff if not the last attempt
            if attempt < retries - 1 and backoff:
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
    
    # If we got here, all retries failed
    raise last_exception

def verify_memory_write(memory, doc_text: str, agent_name: str, metadata: Dict[str, Any]) -> bool:
    """
    Write to memory and verify the write was successful by querying it back.
    
    Args:
        memory: Memory instance
        doc_text: Text to store
        agent_name: Name of the agent
        metadata: Metadata for the document
        
    Returns:
        True if verification was successful, False otherwise
    """
    # Define a unique query key from metadata
    query_key = next((f"{k}:{v}" for k, v in metadata.items() if k != 'timestamp'), None)
    
    if not query_key:
        # If no good query key exists, use the type
        query_key = f"type:{metadata.get('type', 'unknown')}"
    
    try:
        # Store in memory
        memory.add_document(doc_text, agent_name, metadata=metadata)
        
        # Immediately verify by querying
        logger.debug(f"Verifying memory write with query: {query_key}")
        results = memory.query_memory(query_key, agent_name=agent_name)
        
        if results:
            logger.debug(f"Successfully verified memory write: found {len(results)} matching documents")
            return True
        else:
            logger.warning(f"Failed to verify memory write - no results found for query: {query_key}")
            return False
    except Exception as e:
        logger.error(f"Error in memory write/verification: {str(e)}")
        return False 