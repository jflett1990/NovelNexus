import logging
import json
import re
from typing import Dict, Any, List, Optional, Union, Callable
import uuid
import traceback

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def validate_and_fix(
    data: Any,
    validator_func: Callable,
    agent_name: str,
    log_raw_on_error: bool = True
) -> Dict[str, Any]:
    """
    Central validation function that applies a specific validator and handles errors.
    
    Args:
        data: The data to validate
        validator_func: The specific validation function to apply
        agent_name: Name of the agent for logging
        log_raw_on_error: Whether to log the raw data on error
        
    Returns:
        Validated and fixed data
    """
    try:
        # If data is a string (raw JSON or text), try to parse it
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from {agent_name} output. Error: {str(e)}")
                # We'll let the specific validator handle text parsing as fallback
        
        # Apply the specific validator
        validated_data = validator_func(data)
        return validated_data
    
    except Exception as e:
        logger.error(f"Validation error for {agent_name}: {str(e)}")
        if log_raw_on_error:
            logger.debug(f"Raw data that failed validation: {data}")
        logger.debug(traceback.format_exc())
        
        # Attempt to create a minimal valid structure based on agent type
        if 'character' in agent_name:
            return {"characters": []}
        elif 'world' in agent_name:
            return {"name": "Default World", "locations": [], "cultural_elements": []}
        elif 'idea' in agent_name:
            return {"ideas": []}
        elif 'plot' in agent_name or 'chapter_plan' in agent_name:
            return {"chapters": []}
        elif 'research' in agent_name:
            return {"topics": [], "detailed_research": [], "synthesis": {}}
        elif 'manuscript' in agent_name or 'chapter_writer' in agent_name:
            return {"title": "Default Chapter", "content": "Error generating content."}
        else:
            # Generic fallback
            return {}

def validate_character_agent(data: Any) -> Dict[str, Any]:
    """
    Validate and fix character agent output.
    
    Args:
        data: Character data to validate
        
    Returns:
        Validated and structured character data
    """
    # If we received a list directly, wrap it in a dict
    if isinstance(data, list):
        data = {"characters": data}
    
    # If we received a dict without characters key
    if isinstance(data, dict) and "characters" not in data:
        # Check if it looks like a single character
        if "name" in data or "role" in data:
            data = {"characters": [data]}
        else:
            # Search for any list that might contain characters
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    if "name" in value[0] or "role" in value[0]:
                        data = {"characters": value}
                        break
    
    # Ensure we have a characters key with a list
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data)}")
    
    if "characters" not in data:
        data["characters"] = []
    
    if not isinstance(data["characters"], list):
        data["characters"] = [data["characters"]]
    
    # Validate each character
    for i, char in enumerate(data["characters"]):
        if not isinstance(char, dict):
            data["characters"][i] = {"name": f"Character {i+1}"}
            continue
        
        # Ensure required fields
        if "name" not in char or not char["name"]:
            char["name"] = f"Character {i+1}"
        
        if "role" not in char or not char["role"]:
            char["role"] = "Supporting Character"
        
        if "personality" not in char or not char["personality"]:
            char["personality"] = "Complex personality appropriate for their role"
        
        if "background" not in char or not char["background"]:
            char["background"] = "Unknown background"
        
        # Ensure relationships is a list
        if "relationships" not in char:
            char["relationships"] = []
        elif not isinstance(char["relationships"], list):
            char["relationships"] = [char["relationships"]]
    
    return data

def validate_world_building(data: Any) -> Dict[str, Any]:
    """
    Validate and fix world building agent output.
    
    Args:
        data: World building data to validate
        
    Returns:
        Validated and structured world data
    """
    # Handle string input (try to parse as JSON, or extract structured info)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # Attempt basic structure extraction if JSON parsing fails
            world_name_match = re.search(r"world(?:\s+name)?[\s:]+([^\n]+)", data, re.IGNORECASE)
            world_name = world_name_match.group(1) if world_name_match else "Unnamed World"
            
            # Extract locations using pattern matching
            locations = []
            location_blocks = re.findall(r"(?:location|place|setting)(?:\s+\d+)?[\s:]+([^\n]+)(?:\n+(?:description|details?)[\s:]+([^\n]+))?", data, re.IGNORECASE)
            for loc_name, loc_desc in location_blocks:
                locations.append({"name": loc_name.strip(), "description": loc_desc.strip() if loc_desc else "No description"})
            
            # Create basic structure
            data = {
                "name": world_name.strip(),
                "locations": locations,
                "cultural_elements": []
            }
    
    # If we get a list, try to determine if it's locations or cultural elements
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict):
            if "location" in data[0] or "place" in data[0] or "name" in data[0]:
                data = {"name": "Generated World", "locations": data, "cultural_elements": []}
            else:
                data = {"name": "Generated World", "locations": [], "cultural_elements": data}
        else:
            data = {"name": "Generated World", "locations": [], "cultural_elements": []}
    
    # Ensure we have a dict with required keys
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data)}")
    
    if "name" not in data or not data["name"]:
        data["name"] = "Unnamed World"
    
    if "locations" not in data:
        data["locations"] = []
    elif not isinstance(data["locations"], list):
        data["locations"] = [data["locations"]]
    
    if "cultural_elements" not in data:
        data["cultural_elements"] = []
    elif not isinstance(data["cultural_elements"], list):
        data["cultural_elements"] = [data["cultural_elements"]]
    
    # Validate locations
    for i, loc in enumerate(data["locations"]):
        if not isinstance(loc, dict):
            data["locations"][i] = {"name": f"Location {i+1}", "description": "Unknown location"}
            continue
            
        if "name" not in loc or not loc["name"]:
            loc["name"] = f"Location {i+1}"
        
        if "description" not in loc or not loc["description"]:
            loc["description"] = "No description available"
    
    # Validate cultural elements
    for i, elem in enumerate(data["cultural_elements"]):
        if not isinstance(elem, dict):
            data["cultural_elements"][i] = {"name": f"Cultural Element {i+1}", "description": "Unknown cultural element"}
            continue
            
        if "name" not in elem or not elem["name"]:
            elem["name"] = f"Cultural Element {i+1}"
        
        if "description" not in elem or not elem["description"]:
            elem["description"] = "No description available"
    
    return data

def validate_ideation(data: Any) -> Dict[str, Any]:
    """
    Validate and fix ideation agent output.
    
    Args:
        data: Ideation data to validate
        
    Returns:
        Validated and structured ideation data
    """
    # Handle string input (try to parse as JSON, or extract structured info)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # Attempt to extract ideas using regex
            idea_blocks = re.findall(r"(?:idea|concept)(?:\s+\d+)?[\s:]+([^\n]+)(?:\n+(?:description|summary)[\s:]+([^\n]+))?", data, re.IGNORECASE)
            ideas = []
            for i, (title, desc) in enumerate(idea_blocks):
                ideas.append({
                    "id": str(uuid.uuid4()),
                    "title": title.strip(),
                    "description": desc.strip() if desc else "No description",
                    "score": 0
                })
            data = {"ideas": ideas}
    
    # If we received a list directly, assume it's a list of ideas
    if isinstance(data, list):
        data = {"ideas": data}
    
    # If we have a dict without ideas key but with title/description, treat as single idea
    if isinstance(data, dict) and "ideas" not in data and ("title" in data or "concept" in data):
        data = {"ideas": [data]}
    
    # Ensure we have a dict with ideas key
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data)}")
    
    # Look for various key names that might contain ideas
    idea_key = None
    for key in ["ideas", "concepts", "book_ideas", "story_ideas"]:
        if key in data and (isinstance(data[key], list) or isinstance(data[key], dict)):
            idea_key = key
            break
    
    # If no ideas key found, create empty list
    if idea_key is None:
        data["ideas"] = []
    else:
        # Standardize to "ideas" key
        data["ideas"] = data[idea_key]
        if idea_key != "ideas":
            del data[idea_key]
    
    # Ensure ideas is a list
    if not isinstance(data["ideas"], list):
        data["ideas"] = [data["ideas"]]
    
    # Validate each idea
    for i, idea in enumerate(data["ideas"]):
        if not isinstance(idea, dict):
            data["ideas"][i] = {
                "id": str(uuid.uuid4()),
                "title": f"Idea {i+1}",
                "description": str(idea) if idea else "No description",
                "score": 0
            }
            continue
        
        # Ensure required fields
        if "id" not in idea or not idea["id"]:
            idea["id"] = str(uuid.uuid4())
        
        if "title" not in idea or not idea["title"]:
            idea["title"] = f"Idea {i+1}"
        
        if "description" not in idea or not idea["description"]:
            if "summary" in idea:
                idea["description"] = idea["summary"]
            else:
                idea["description"] = "No description available"
        
        if "score" not in idea:
            idea["score"] = 0
        else:
            try:
                idea["score"] = float(idea["score"])
            except (ValueError, TypeError):
                idea["score"] = 0
    
    return data

def validate_plot_chapters(data: Any) -> Dict[str, Any]:
    """
    Validate and fix plot/chapter planning agent output.
    
    Args:
        data: Plot/Chapter data to validate
        
    Returns:
        Validated and structured plot/chapter data
    """
    # Handle string input (try to parse as JSON, or extract structured info)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # Attempt to extract chapters using regex
            chapter_blocks = re.findall(r"(?:chapter|scene)(?:\s+(\d+))?[\s:]+([^\n]+)(?:\n+(?:summary|description)[\s:]+([^\n]+))?", data, re.IGNORECASE)
            chapters = []
            for i, (number, title, summary) in enumerate(chapter_blocks):
                chapters.append({
                    "number": int(number) if number else i+1,
                    "title": title.strip(),
                    "summary": summary.strip() if summary else "No summary available"
                })
            data = {"chapters": chapters}
    
    # If we received a list directly, assume it's a list of chapters
    if isinstance(data, list):
        data = {"chapters": data}
    
    # If we have a dict without chapters key but with title/summary, treat as single chapter
    if isinstance(data, dict) and "chapters" not in data and ("title" in data or "summary" in data):
        data = {"chapters": [data]}
    
    # Ensure we have a dict with chapters key
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data)}")
    
    # Look for various key names that might contain chapters
    chapter_key = None
    for key in ["chapters", "scenes", "plot_points", "outline"]:
        if key in data and (isinstance(data[key], list) or isinstance(data[key], dict)):
            chapter_key = key
            break
    
    # If no chapters key found, create empty list
    if chapter_key is None:
        data["chapters"] = []
    else:
        # Standardize to "chapters" key
        data["chapters"] = data[chapter_key]
        if chapter_key != "chapters":
            del data[chapter_key]
    
    # Ensure chapters is a list
    if not isinstance(data["chapters"], list):
        data["chapters"] = [data["chapters"]]
    
    # Validate each chapter
    for i, chapter in enumerate(data["chapters"]):
        if not isinstance(chapter, dict):
            data["chapters"][i] = {
                "number": i+1,
                "title": f"Chapter {i+1}",
                "summary": str(chapter) if chapter else "No summary available"
            }
            continue
        
        # Ensure required fields
        if "number" not in chapter or not chapter["number"]:
            chapter["number"] = i+1
        else:
            try:
                chapter["number"] = int(chapter["number"])
            except (ValueError, TypeError):
                chapter["number"] = i+1
        
        if "title" not in chapter or not chapter["title"]:
            chapter["title"] = f"Chapter {chapter['number']}"
        
        if "summary" not in chapter or not chapter["summary"]:
            if "description" in chapter:
                chapter["summary"] = chapter["description"]
            else:
                chapter["summary"] = "No summary available"
    
    return data

def validate_research(data: Any) -> Dict[str, Any]:
    """
    Validate and fix research agent output.
    
    Args:
        data: Research data to validate
        
    Returns:
        Validated and structured research data
    """
    # Handle string input (try to parse as JSON, or extract structured info)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # For text input, treat the whole text as a synthesis
            data = {
                "topics": [],
                "detailed_research": [],
                "synthesis": {"content": data}
            }
    
    # Ensure we have a dict
    if not isinstance(data, dict):
        if isinstance(data, list):
            # If we got a list, assume it's a list of topics
            data = {"topics": data, "detailed_research": [], "synthesis": {}}
        else:
            raise ValidationError(f"Expected dict or list, got {type(data)}")
    
    # Ensure required keys exist
    if "topics" not in data:
        data["topics"] = []
    elif not isinstance(data["topics"], list):
        data["topics"] = [data["topics"]]
    
    if "detailed_research" not in data:
        # Look for alternative keys
        research_key = None
        for key in ["research", "findings", "details", "sources"]:
            if key in data and (isinstance(data[key], list) or isinstance(data[key], dict)):
                research_key = key
                break
        
        if research_key:
            data["detailed_research"] = data[research_key]
            if research_key != "detailed_research":
                del data[research_key]
        else:
            data["detailed_research"] = []
    
    if not isinstance(data["detailed_research"], list):
        data["detailed_research"] = [data["detailed_research"]]
    
    if "synthesis" not in data:
        # Look for alternative keys
        synthesis_key = None
        for key in ["summary", "overview", "conclusion"]:
            if key in data and isinstance(data[key], (dict, str)):
                synthesis_key = key
                break
        
        if synthesis_key:
            if isinstance(data[synthesis_key], str):
                data["synthesis"] = {"content": data[synthesis_key]}
            else:
                data["synthesis"] = data[synthesis_key]
            if synthesis_key != "synthesis":
                del data[synthesis_key]
        else:
            data["synthesis"] = {}
    
    if not isinstance(data["synthesis"], dict):
        data["synthesis"] = {"content": str(data["synthesis"])}
    
    # Validate topics
    for i, topic in enumerate(data["topics"]):
        if not isinstance(topic, dict):
            data["topics"][i] = {
                "id": str(uuid.uuid4()),
                "name": str(topic) if topic else f"Topic {i+1}",
                "description": "No description available"
            }
            continue
        
        # Ensure required fields
        if "id" not in topic or not topic["id"]:
            topic["id"] = str(uuid.uuid4())
        
        if "name" not in topic or not topic["name"]:
            topic["name"] = f"Topic {i+1}"
        
        if "description" not in topic or not topic["description"]:
            if "summary" in topic:
                topic["description"] = topic["summary"]
            else:
                topic["description"] = "No description available"
    
    # Validate detailed research
    for i, research in enumerate(data["detailed_research"]):
        if not isinstance(research, dict):
            data["detailed_research"][i] = {
                "id": str(uuid.uuid4()),
                "title": f"Research {i+1}",
                "content": str(research) if research else "No content available"
            }
            continue
        
        # Ensure required fields
        if "id" not in research or not research["id"]:
            research["id"] = str(uuid.uuid4())
        
        if "title" not in research or not research["title"]:
            if "name" in research:
                research["title"] = research["name"]
            else:
                research["title"] = f"Research {i+1}"
        
        if "content" not in research or not research["content"]:
            if "findings" in research:
                research["content"] = research["findings"]
            elif "description" in research:
                research["content"] = research["description"]
            else:
                research["content"] = "No content available"
    
    # Validate synthesis
    if "content" not in data["synthesis"] or not data["synthesis"]["content"]:
        if len(data["topics"]) > 0:
            data["synthesis"]["content"] = f"Research on {len(data['topics'])} topics."
        else:
            data["synthesis"]["content"] = "No synthesis available."
    
    return data

def validate_relationships(data: Any, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and fix character relationships.
    
    Args:
        data: Relationship data to validate
        characters: List of characters to validate against
        
    Returns:
        Validated and structured relationships list
    """
    # Handle string input (try to parse as JSON)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # For unparseable strings, return empty list
            return []
    
    # Ensure we have a list
    if not isinstance(data, list):
        if isinstance(data, dict) and ("character1" in data or "character2" in data or "character1_id" in data or "character2_id" in data):
            # Single relationship object
            data = [data]
        else:
            # Look for a list in the dict
            relationship_key = None
            for key in ["relationships", "character_relationships", "connections"]:
                if key in data and isinstance(data[key], (list, dict)):
                    relationship_key = key
                    break
            
            if relationship_key:
                rel_data = data[relationship_key]
                if isinstance(rel_data, dict) and ("character1" in rel_data or "character2" in rel_data):
                    data = [rel_data]
                elif isinstance(rel_data, list):
                    data = rel_data
                else:
                    data = []
            else:
                data = []
    
    # Create set of character names for easy lookup
    character_names = {char.get("name", "").lower() for char in characters if isinstance(char, dict) and "name" in char}
    
    # Validate each relationship
    valid_relationships = []
    for i, rel in enumerate(data):
        if not isinstance(rel, dict):
            continue
        
        # Get character names
        char1 = rel.get("character1") or rel.get("character1_id") or rel.get("char1")
        char2 = rel.get("character2") or rel.get("character2_id") or rel.get("char2")
        
        if not char1 or not char2:
            continue
        
        # Standardize keys
        valid_rel = {
            "character1": char1,
            "character2": char2,
            "relationship_type": rel.get("relationship_type") or rel.get("type") or "Unknown",
            "dynamics": rel.get("dynamics") or rel.get("description") or "No dynamics specified",
        }
        
        # Add additional fields if present
        if "history" in rel:
            valid_rel["history"] = rel["history"]
        
        if "story_impact" in rel:
            valid_rel["story_impact"] = rel["story_impact"]
        
        # Only include if at least one character exists in our character list
        if (valid_rel["character1"].lower() in character_names or 
            valid_rel["character2"].lower() in character_names):
            valid_relationships.append(valid_rel)
    
    return valid_relationships

def validate_manuscript_chapter(data: Any) -> Dict[str, Any]:
    """
    Validate and fix manuscript/chapter writer output.
    
    Args:
        data: Manuscript/chapter data to validate
        
    Returns:
        Validated and structured manuscript/chapter data
    """
    # Handle string input (treat as chapter content)
    if isinstance(data, str):
        # Clean up the string (remove HTML and markdown if needed)
        content = data
        
        # Try to extract title from the string
        title_match = re.search(r"^#\s+(.+)$", data, re.MULTILINE)
        title = title_match.group(1) if title_match else "Untitled Chapter"
        
        return {
            "title": title,
            "content": content
        }
    
    # Ensure we have a dict
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict or string, got {type(data)}")
    
    # Extract basic fields
    result = {}
    
    # Extract title
    if "title" in data:
        result["title"] = data["title"]
    elif "chapter_title" in data:
        result["title"] = data["chapter_title"]
    else:
        result["title"] = "Untitled Chapter"
    
    # Extract content
    if "content" in data:
        result["content"] = data["content"]
    elif "chapter_content" in data:
        result["content"] = data["chapter_content"]
    elif "text" in data:
        result["content"] = data["text"]
    elif "body" in data:
        result["content"] = data["body"]
    else:
        result["content"] = "No content available"
    
    # Extract number if available
    if "number" in data:
        result["number"] = data["number"]
    elif "chapter_number" in data:
        result["chapter_number"] = data["chapter_number"]
    
    # Return validated chapter
    return result

# Convenience functions for each agent type
def validate_characters(data: Any) -> Dict[str, Any]:
    """Validate character agent output."""
    return validate_and_fix(data, validate_character_agent, "character_agent")

def validate_world(data: Any) -> Dict[str, Any]:
    """Validate world building agent output."""
    return validate_and_fix(data, validate_world_building, "world_building_agent")

def validate_ideas(data: Any) -> Dict[str, Any]:
    """Validate ideation agent output."""
    return validate_and_fix(data, validate_ideation, "ideation_agent")

def validate_plot(data: Any) -> Dict[str, Any]:
    """Validate plot/chapter planning agent output."""
    return validate_and_fix(data, validate_plot_chapters, "plot_agent")

def validate_research_data(data: Any) -> Dict[str, Any]:
    """Validate research agent output."""
    return validate_and_fix(data, validate_research, "research_agent")

def validate_chapter(data: Any) -> Dict[str, Any]:
    """Validate chapter writer output."""
    return validate_and_fix(data, validate_manuscript_chapter, "chapter_writer_agent")

def validate_character_relationships(data: Any, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate character relationships with reference to existing characters."""
    try:
        return validate_relationships(data, characters)
    except Exception as e:
        logger.error(f"Validation error for character relationships: {str(e)}")
        logger.debug(traceback.format_exc())
        return [] 