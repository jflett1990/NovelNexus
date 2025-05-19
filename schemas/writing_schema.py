"""
Schema definition for written chapter outputs.
"""

WRITING_SCHEMA = {
    "type": "object",
    "required": ["id", "title", "content"],
    "properties": {
        "id": {
            "type": "string",
            "description": "Unique identifier for the chapter"
        },
        "number": {
            "type": "integer",
            "description": "Chapter number"
        },
        "title": {
            "type": "string",
            "description": "Chapter title"
        },
        "content": {
            "type": "string",
            "description": "Full text content of the chapter"
        },
        "word_count": {
            "type": "integer",
            "description": "Word count of the chapter"
        },
        "summary": {
            "type": "string",
            "description": "Brief summary of the chapter content"
        },
        "pov_character": {
            "type": "string",
            "description": "Point-of-view character for this chapter"
        },
        "featured_characters": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Characters featured in this chapter"
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Locations featured in this chapter"
        },
        "scene_breaks": {
            "type": "array",
            "items": {
                "type": "integer"
            },
            "description": "Positions of scene breaks in the content (character indices)"
        },
        "themes_explored": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Themes explored in this chapter"
        },
        "writing_style": {
            "type": "object",
            "properties": {
                "pov": {
                    "type": "string",
                    "description": "Point of view (first person, third person limited, etc.)"
                },
                "tense": {
                    "type": "string",
                    "description": "Tense (past, present)"
                },
                "tone": {
                    "type": "string",
                    "description": "Overall tone of the chapter"
                }
            }
        },
        "creation_date": {
            "type": "string",
            "description": "Date when the chapter was created"
        },
        "revision_notes": {
            "type": "object",
            "properties": {
                "revision_date": {
                    "type": "string",
                    "description": "Date of the last revision"
                },
                "revisions_made": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of revisions made"
                }
            }
        }
    }
}
