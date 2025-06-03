"""
Schema definition for research outputs.
"""

RESEARCH_SCHEMA = {
    "type": "object",
    "required": ["topics"],
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "description", "importance", "key_questions"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique identifier for the research topic"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the research topic"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the topic and why it needs research"
                    },
                    "importance": {
                        "type": "string",
                        "description": "Why this research is important for the book"
                    },
                    "key_questions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Key questions that need to be answered through research"
                    },
                    "preliminary_information": {
                        "type": "string",
                        "description": "Basic information that's already known without specialized research"
                    },
                    "potential_sources": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Potential sources or methods for researching this topic"
                    },
                    "related_topics": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Related research topics"
                    },
                    "complexity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Complexity level of the research topic"
                    },
                    "impact_areas": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Areas of the book that will be impacted by this research"
                    },
                    "priority": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Priority level (1-10) of this research topic"
                    }
                }
            }
        },
        "overall_focus": {
            "type": "string",
            "description": "Overall focus and direction of the research effort"
        },
        "recommended_approach": {
            "type": "string",
            "description": "Recommended approach to conducting the research"
        },
        "research_timeline": {
            "type": "string",
            "description": "Suggested timeline or ordering for conducting the research"
        }
    }
}
