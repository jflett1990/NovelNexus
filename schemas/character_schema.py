"""
Schema definition for character outputs.
"""

CHARACTER_SCHEMA = {
    "type": "object",
    "required": ["characters"],
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "role", "brief_description", "background"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique identifier for the character"
                    },
                    "name": {
                        "type": "string",
                        "description": "Character's full name"
                    },
                    "role": {
                        "type": "string",
                        "description": "Character's role in the story (e.g., protagonist, antagonist, supporting)"
                    },
                    "brief_description": {
                        "type": "string",
                        "description": "1-2 sentence summary of the character"
                    },
                    "background": {
                        "type": "string",
                        "description": "Character's history and background"
                    },
                    "physical_description": {
                        "type": "string",
                        "description": "Character's physical appearance"
                    },
                    "personality": {
                        "type": "object",
                        "properties": {
                            "traits": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Key personality traits"
                            },
                            "strengths": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Character strengths"
                            },
                            "flaws": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Character flaws"
                            },
                            "description": {
                                "type": "string",
                                "description": "Detailed description of personality"
                            }
                        }
                    },
                    "motivations": {
                        "type": "object",
                        "properties": {
                            "primary": {
                                "type": "string",
                                "description": "Primary motivation driving the character"
                            },
                            "secondary": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Secondary motivations"
                            },
                            "fears": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Character's fears and insecurities"
                            },
                            "desires": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Character's desires and wants"
                            }
                        }
                    },
                    "arc": {
                        "type": "object",
                        "properties": {
                            "starting_point": {
                                "type": "string",
                                "description": "Character's state at the beginning of the story"
                            },
                            "journey": {
                                "type": "string",
                                "description": "Character's development journey"
                            },
                            "ending_point": {
                                "type": "string",
                                "description": "Character's state at the end of the story"
                            },
                            "key_moments": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Key moments in the character's arc"
                            }
                        }
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "character": {
                                    "type": "string",
                                    "description": "Name of the related character"
                                },
                                "relationship_type": {
                                    "type": "string",
                                    "description": "Type of relationship (e.g., friend, enemy, family)"
                                },
                                "dynamics": {
                                    "type": "string",
                                    "description": "Dynamics of the relationship"
                                }
                            }
                        },
                        "description": "Character's relationships with other characters"
                    },
                    "voice": {
                        "type": "string",
                        "description": "Character's voice, speech patterns, and typical expressions"
                    },
                    "backstory": {
                        "type": "string",
                        "description": "Detailed backstory of the character, including formative events"
                    },
                    "goals": {
                        "type": "object",
                        "properties": {
                            "short_term": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Short-term goals"
                            },
                            "long_term": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Long-term goals"
                            }
                        }
                    }
                }
            }
        }
    }
}
