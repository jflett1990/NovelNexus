"""
Schema definition for chapter review outputs.
"""

REVIEW_SCHEMA = {
    "type": "object",
    "required": ["chapter_id", "overall_assessment"],
    "properties": {
        "id": {
            "type": "string",
            "description": "Unique identifier for the review"
        },
        "chapter_id": {
            "type": "string",
            "description": "ID of the chapter being reviewed"
        },
        "chapter_number": {
            "type": "integer",
            "description": "Chapter number"
        },
        "chapter_title": {
            "type": "string",
            "description": "Chapter title"
        },
        "review_date": {
            "type": "string",
            "description": "Date when the review was conducted"
        },
        "overall_assessment": {
            "type": "object",
            "required": ["rating", "summary", "strengths", "weaknesses"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Overall rating (1-10)"
                },
                "summary": {
                    "type": "string",
                    "description": "Summary assessment of the chapter"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Key strengths of the chapter"
                },
                "weaknesses": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Key weaknesses of the chapter"
                }
            }
        },
        "plot_structure": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for plot and structure (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of plot and structure"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with plot and structure"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in plot and structure"
                }
            }
        },
        "character_development": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for character development (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of character development"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with character development"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in character development"
                }
            }
        },
        "setting_atmosphere": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for setting and atmosphere (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of setting and atmosphere"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with setting and atmosphere"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in setting and atmosphere"
                }
            }
        },
        "dialogue": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for dialogue (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of dialogue"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with dialogue"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in dialogue"
                }
            }
        },
        "pacing_flow": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for pacing and flow (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of pacing and flow"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with pacing and flow"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in pacing and flow"
                }
            }
        },
        "prose_quality": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for prose quality (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of prose quality"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with prose quality"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in prose quality"
                }
            }
        },
        "style_consistency": {
            "type": "object",
            "required": ["rating", "assessment", "issues", "strengths"],
            "properties": {
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Rating for style consistency (1-10)"
                },
                "assessment": {
                    "type": "string",
                    "description": "Assessment of style consistency"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the issue"
                            },
                            "example": {
                                "type": "string",
                                "description": "Example from the text"
                            },
                            "suggestion": {
                                "type": "string",
                                "description": "Suggestion for improvement"
                            }
                        }
                    },
                    "description": "Issues with style consistency"
                },
                "strengths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Strengths in style consistency"
                }
            }
        },
        "priority_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Area of focus for the recommendation"
                    },
                    "recommendation": {
                        "type": "string",
                        "description": "Detailed recommendation"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Priority level of the recommendation"
                    }
                }
            },
            "description": "Prioritized recommendations for improvement"
        },
        "next_steps": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Suggested next steps for revision"
        }
    }
}
