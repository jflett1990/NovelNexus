"""
Schema definition for ideation outputs.
"""

IDEATION_SCHEMA = {
    "type": "object",
    "required": ["ideas"],
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "genre", "target_audience", "themes", "plot_summary", "score"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique identifier for the idea"
                    },
                    "title": {
                        "type": "string",
                        "description": "Proposed title for the book"
                    },
                    "genre": {
                        "type": "string",
                        "description": "Primary genre of the book"
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "Target audience for the book (e.g., YA, Adult, Middle Grade)"
                    },
                    "themes": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Key themes explored in the book"
                    },
                    "plot_summary": {
                        "type": "string",
                        "description": "Brief summary of the plot (200-300 words)"
                    },
                    "main_character": {
                        "type": "string",
                        "description": "Brief description of the main character"
                    },
                    "hook": {
                        "type": "string",
                        "description": "The central hook or premise that makes this idea compelling"
                    },
                    "conflict": {
                        "type": "string",
                        "description": "The central conflict driving the story"
                    },
                    "unique_elements": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Unique elements that make this idea stand out"
                    },
                    "market_potential": {
                        "type": "string",
                        "description": "Assessment of market potential and audience appeal"
                    },
                    "comparable_works": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Similar books or works that might appeal to the same audience"
                    },
                    "score": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Overall assessment score (1-10) of the idea's potential"
                    }
                }
            }
        }
    }
}
