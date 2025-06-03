import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Define style reference dictionary with literary tones
STYLE_REFERENCES = {
    "literary": {
        "description": "sophisticated, reflective, nuanced",
        "positive_traits": [
            "Use nuanced character psychology",
            "Develop complex thematic elements",
            "Employ deliberate, precise language"
        ],
        "negative_traits": [
            "Formulaic plot structures",
            "Simplistic character motivations",
            "Excessive exposition"
        ]
    },
    "atwood": {
        "description": "precise, observant, ironic",
        "positive_traits": [
            "Use sharp, precise descriptions that reveal character",
            "Include feminist themes and power dynamics subtly",
            "Employ controlled, understated irony"
        ],
        "negative_traits": [
            "Overly dramatic emotional displays",
            "Heavy-handed moralizing",
            "Unnecessarily complex syntax"
        ]
    },
    "murakami": {
        "description": "surreal, introspective, dreamlike",
        "positive_traits": [
            "Blend mundane reality with surreal elements",
            "Use precise, simple language for complex ideas",
            "Include everyday rituals described in detail"
        ],
        "negative_traits": [
            "Explaining the surreal elements explicitly",
            "Over-resolving narrative mysteries",
            "Conventional plot structures"
        ]
    },
    "faulkner": {
        "description": "dense, nonlinear, Southern Gothic",
        "positive_traits": [
            "Use stream-of-consciousness and fractured chronology",
            "Create complex sentence structures with nested clauses",
            "Emphasize regional dialect and idiom"
        ],
        "negative_traits": [
            "Simple, linear plotting",
            "Straightforward exposition",
            "Underexplained family connections"
        ]
    },
    "hemingway": {
        "description": "sparse, direct, restrained",
        "positive_traits": [
            "Use short, declarative sentences",
            "Convey emotion through action and dialogue",
            "Leave critical elements understated or implied"
        ],
        "negative_traits": [
            "Flowery or ornate descriptions",
            "Excessive internal monologue",
            "Overt emotional statements"
        ]
    }
}

def get_style_reference(style: str) -> Dict[str, Any]:
    """
    Fetches the stylistic tone definition for a given author or style.
    
    Args:
        style: The name of the style (e.g., "murakami", "literary")
        
    Returns:
        Dictionary with style information
    """
    # Default to "literary" if style not found
    if style not in STYLE_REFERENCES:
        logger.warning(f"Style '{style}' not found, defaulting to 'literary'")
        return STYLE_REFERENCES["literary"]
    
    return STYLE_REFERENCES[style]

def build_stylistic_guidelines(style: str, themes: Optional[List[str]] = None) -> str:
    """
    Constructs inline stylistic rules with positive and negative constraints.
    
    Args:
        style: The name of the style (e.g., "murakami", "literary")
        themes: Optional list of themes to incorporate
        
    Returns:
        Formatted guidelines string
    """
    style_ref = get_style_reference(style)
    
    guidelines = f"Write in the style of {style.title()}:\n"
    guidelines += f"{style_ref['description']}.\n\n"
    
    # Add positive traits
    guidelines += "Focus on:\n"
    for trait in style_ref["positive_traits"]:
        guidelines += f"- {trait}.\n"
    
    # Add theme guidance if provided
    if themes and len(themes) > 0:
        guidelines += f"\nIncorporate these themes: {', '.join(themes)}.\n"
    
    # Add negative traits
    guidelines += "\nAvoid:\n"
    for trait in style_ref["negative_traits"]:
        guidelines += f"- {trait}.\n"
    
    # Add universal AI writing avoidance points
    guidelines += "- Common tropes and clichés.\n"
    guidelines += "- Narrative voice that sounds like AI.\n"
    guidelines += "- Overuse of dialogue tags or exposition.\n"
    
    return guidelines

def prime_prompt(base_prompt: str, style: str = "literary", themes: Optional[List[str]] = None) -> str:
    """
    Appends stylistic guidelines to a base prompt to prime the model.
    
    Args:
        base_prompt: The core instruction prompt
        style: The name of the style (e.g., "murakami", "literary")
        themes: Optional list of themes to incorporate
        
    Returns:
        Enhanced prompt with style guidelines
    """
    guidelines = build_stylistic_guidelines(style, themes)
    
    # Combine prompts with clear separation
    enhanced_prompt = f"{base_prompt}\n\n--- WRITING STYLE GUIDELINES ---\n{guidelines}"
    
    return enhanced_prompt 