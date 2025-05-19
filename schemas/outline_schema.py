"""
Schema definition for book outline outputs.
"""

OUTLINE_SCHEMA = {
    "type": "object",
    "required": ["title", "structure", "chapters"],
    "properties": {
        "title": {
            "type": "string",
            "description": "Title of the book"
        },
        "genre": {
            "type": "string",
            "description": "Genre of the book"
        },
        "target_audience": {
            "type": "string",
            "description": "Target audience for the book"
        },
        "estimated_word_count": {
            "type": "integer",
            "description": "Estimated total word count"
        },
        "structure": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Structure type (e.g., three-act, hero's journey, etc.)"
                },
                "description": {
                    "type": "string",
                    "description": "Description of the overall structure"
                },
                "acts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the act"
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of the act's purpose"
                            },
                            "chapters": {
                                "type": "array",
                                "items": {
                                    "type": "integer"
                                },
                                "description": "Chapter numbers included in this act"
                            }
                        }
                    }
                }
            }
        },
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Theme name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of how the theme develops"
                    }
                }
            }
        },
        "character_arcs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character": {
                        "type": "string",
                        "description": "Character name"
                    },
                    "arc_type": {
                        "type": "string",
                        "description": "Type of character arc"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the character's development"
                    },
                    "key_moments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chapter": {
                                    "type": "integer",
                                    "description": "Chapter number where this moment occurs"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Description of the key moment"
                                }
                            }
                        }
                    }
                }
            }
        },
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "number", "title", "summary"],
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
                    "pov_character": {
                        "type": "string",
                        "description": "Point-of-view character for this chapter"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Summary of the chapter's content"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Purpose or function of this chapter in the overall story"
                    },
                    "word_count_estimate": {
                        "type": "integer",
                        "description": "Estimated word count for this chapter"
                    },
                    "scenes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Summary of the scene"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "Location where the scene takes place"
                                },
                                "characters": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "Characters present in the scene"
                                },
                                "purpose": {
                                    "type": "string",
                                    "description": "Purpose or function of this scene"
                                },
                                "conflict": {
                                    "type": "string",
                                    "description": "Conflict or tension in the scene"
                                },
                                "outcome": {
                                    "type": "string",
                                    "description": "Outcome or resolution of the scene"
                                }
                            }
                        }
                    },
                    "featured_characters": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Characters featured in this chapter"
                    },
                    "plot_development": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Plot developments in this chapter"
                    },
                    "character_development": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "character": {
                                    "type": "string",
                                    "description": "Character name"
                                },
                                "development": {
                                    "type": "string",
                                    "description": "How the character develops in this chapter"
                                }
                            }
                        }
                    },
                    "theme_exploration": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "theme": {
                                    "type": "string",
                                    "description": "Theme name"
                                },
                                "exploration": {
                                    "type": "string",
                                    "description": "How the theme is explored in this chapter"
                                }
                            }
                        }
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes or considerations for this chapter"
                    }
                }
            }
        }
    }
}
