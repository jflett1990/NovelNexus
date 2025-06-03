"""
Schema definition for world building outputs.
"""

WORLD_BUILDING_SCHEMA = {
    "type": "object",
    "required": ["world_type", "primary_setting", "time_period"],
    "properties": {
        "world_type": {
            "type": "string",
            "description": "Type of world (e.g., fictional, real-world, alternate history, fantasy, sci-fi)"
        },
        "primary_setting": {
            "type": "string",
            "description": "Primary setting or location of the story"
        },
        "time_period": {
            "type": "string",
            "description": "Time period or era in which the story takes place"
        },
        "overview": {
            "type": "string",
            "description": "General overview of the world"
        },
        "physical_environment": {
            "type": "object",
            "properties": {
                "geography": {
                    "type": "string",
                    "description": "Description of the geography and natural features"
                },
                "climate": {
                    "type": "string",
                    "description": "Climate and weather patterns"
                },
                "flora_fauna": {
                    "type": "string",
                    "description": "Notable plants and animals"
                },
                "natural_resources": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Natural resources available"
                }
            }
        },
        "society": {
            "type": "object",
            "properties": {
                "political_structure": {
                    "type": "string",
                    "description": "Political system and governance"
                },
                "economic_system": {
                    "type": "string",
                    "description": "Economic structure and trade"
                },
                "social_structure": {
                    "type": "string",
                    "description": "Social classes and hierarchy"
                },
                "dominant_groups": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Dominant social, political, or cultural groups"
                },
                "marginalized_groups": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Marginalized or oppressed groups"
                }
            }
        },
        "culture": {
            "type": "object",
            "properties": {
                "values": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Core cultural values"
                },
                "beliefs": {
                    "type": "string",
                    "description": "Common beliefs and worldviews"
                },
                "religions": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Religious systems and practices"
                },
                "languages": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Languages spoken"
                },
                "arts": {
                    "type": "string",
                    "description": "Artistic traditions and expressions"
                },
                "cuisine": {
                    "type": "string",
                    "description": "Food culture and traditions"
                }
            }
        },
        "history": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Origin or founding of the world/setting"
                },
                "major_events": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Major historical events"
                },
                "conflicts": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Historical conflicts and wars"
                },
                "technological_development": {
                    "type": "string",
                    "description": "History of technological development"
                }
            }
        },
        "technology": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "description": "Overall technological level"
                },
                "key_technologies": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Key technologies that define the setting"
                },
                "limitations": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Technological limitations"
                },
                "impact": {
                    "type": "string",
                    "description": "Impact of technology on society"
                }
            }
        },
        "magic_supernatural": {
            "type": "object",
            "properties": {
                "exists": {
                    "type": "boolean",
                    "description": "Whether magic or supernatural elements exist"
                },
                "system": {
                    "type": "string",
                    "description": "System or rules governing magic/supernatural"
                },
                "prevalence": {
                    "type": "string",
                    "description": "How common magic/supernatural is"
                },
                "limitations": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Limitations of magic/supernatural"
                },
                "impact": {
                    "type": "string",
                    "description": "Impact of magic/supernatural on society"
                }
            }
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the location"
                    },
                    "type": {
                        "type": "string",
                        "description": "Type of location (e.g., city, forest, landmark)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the location"
                    },
                    "significance": {
                        "type": "string",
                        "description": "Significance to the story"
                    },
                    "inhabitants": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Notable inhabitants or groups"
                    },
                    "features": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Notable features or landmarks"
                    }
                }
            }
        },
        "cultural_elements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "description"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the cultural element"
                    },
                    "type": {
                        "type": "string",
                        "description": "Type of element (e.g., custom, religion, language)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the cultural element"
                    },
                    "significance": {
                        "type": "string",
                        "description": "Cultural significance"
                    },
                    "practitioners": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Groups or individuals who practice/follow this element"
                    }
                }
            }
        },
        "rules_laws": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Important rules, laws, or constraints of the world"
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Current conflicts or tensions in the world"
        },
        "story_relevance": {
            "type": "string",
            "description": "How the world connects to and influences the story"
        }
    }
}
