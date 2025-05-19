"""
Schema definition for final manuscript outputs.
"""

MANUSCRIPT_SCHEMA = {
    "type": "object",
    "required": ["title", "chapters"],
    "properties": {
        "title": {
            "type": "string",
            "description": "Title of the book"
        },
        "subtitle": {
            "type": "string",
            "description": "Subtitle of the book, if applicable"
        },
        "author": {
            "type": "string",
            "description": "Author name"
        },
        "genre": {
            "type": "string",
            "description": "Genre of the book"
        },
        "front_matter": {
            "type": "object",
            "properties": {
                "title_page": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Title as it appears on the title page"
                        },
                        "subtitle": {
                            "type": "string",
                            "description": "Subtitle as it appears on the title page"
                        },
                        "author": {
                            "type": "string",
                            "description": "Author name as it appears on the title page"
                        },
                        "publisher": {
                            "type": "string",
                            "description": "Publisher name, if applicable"
                        }
                    }
                },
                "copyright_page": {
                    "type": "string",
                    "description": "Full text of the copyright page"
                },
                "dedication_page": {
                    "type": "string",
                    "description": "Text of the dedication, if applicable"
                },
                "epigraph": {
                    "type": "string",
                    "description": "Text of the epigraph, if applicable"
                },
                "table_of_contents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the chapter or section"
                            },
                            "page": {
                                "type": "string",
                                "description": "Page number, if applicable"
                            }
                        }
                    },
                    "description": "Table of contents entries"
                }
            }
        },
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "number", "title", "content"],
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
                    }
                }
            }
        },
        "back_matter": {
            "type": "object",
            "properties": {
                "about_the_author": {
                    "type": "string",
                    "description": "About the author text"
                },
                "glossary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term": {
                                "type": "string",
                                "description": "Term being defined"
                            },
                            "definition": {
                                "type": "string",
                                "description": "Definition of the term"
                            }
                        }
                    },
                    "description": "Glossary entries"
                },
                "character_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Character name"
                            },
                            "description": {
                                "type": "string",
                                "description": "Character description"
                            }
                        }
                    },
                    "description": "List of characters"
                },
                "world_description": {
                    "type": "string",
                    "description": "Description of the world/setting"
                },
                "appendices": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Appendix title"
                            },
                            "content": {
                                "type": "string",
                                "description": "Appendix content"
                            }
                        }
                    },
                    "description": "Appendices"
                }
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "creation_date": {
                    "type": "string",
                    "description": "Date when the manuscript was finalized"
                },
                "word_count": {
                    "type": "integer",
                    "description": "Total word count of the manuscript"
                },
                "chapter_count": {
                    "type": "integer",
                    "description": "Total number of chapters"
                },
                "generation_details": {
                    "type": "object",
                    "properties": {
                        "framework_version": {
                            "type": "string",
                            "description": "Version of the generation framework used"
                        },
                        "models_used": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "AI models used in generation"
                        },
                        "generation_time": {
                            "type": "string",
                            "description": "Total time taken to generate the manuscript"
                        }
                    }
                }
            }
        }
    }
}
