"""
OpenAI model configurations for each agent in the NovelNexus system.
This file defines the preferred and fallback models for each agent.
"""

# Model configurations for each agent
AGENT_MODELS = {
    "ideation": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "High creativity, divergent thinking"
    },
    "manuscript": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Longform capability, 1M token context, deep stylistic fidelity"
    },
    "character": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Semantic nuance, relationship mapping"
    },
    "world_building": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Spatial logic, lore continuity"
    },
    "research": {
        "preferred_model": "gpt-3.5-turbo-1106",
        "fallback_model": "gpt-4o",
        "notes": "Factual reasoning, synthesis over narrative tone"
    },
    "outline": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-3.5-turbo-1106",
        "notes": "Logical structure and high instruction-following"
    },
    "review": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Strong editing logic, tone sensitivity"
    },
    "editorial": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Precision editing, clarity enforcement"
    },
    "revision": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Change tracking, stylistic reflow"
    },
    "chapter_planner": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Structural planning, narrative progression"
    },
    "chapter_writer": {
        "preferred_model": "gpt-4.1", 
        "fallback_model": "gpt-4o",
        "notes": "Prose quality, consistent voice"
    },
    "manuscript_refiner": {
        "preferred_model": "gpt-4.1",
        "fallback_model": "gpt-4o",
        "notes": "Literary style enhancement, textural depth"
    }
}

# Embedding model configuration
EMBEDDING_MODEL = "text-embedding-3-large"

def get_agent_model(agent_name: str, use_fallback: bool = False) -> str:
    """
    Get the appropriate model for a given agent.
    
    Args:
        agent_name: Name of the agent
        use_fallback: Whether to use the fallback model
        
    Returns:
        Model name to use
    """
    if agent_name not in AGENT_MODELS:
        # Default to gpt-4o if agent not found
        return "gpt-4o"
    
    if use_fallback and "fallback_model" in AGENT_MODELS[agent_name]:
        return AGENT_MODELS[agent_name]["fallback_model"]
    
    return AGENT_MODELS[agent_name]["preferred_model"] 