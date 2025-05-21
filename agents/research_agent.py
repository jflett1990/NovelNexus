import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.research_schema import RESEARCH_SCHEMA

logger = logging.getLogger(__name__)

class ResearchAgent:
    """
    Agent responsible for generating research and background information for the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Research Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "research_agent"
        self.stage = "research"
    
    def generate_research(
        self,
        book_idea: Dict[str, Any],
        world_data: Optional[Dict[str, Any]] = None,
        num_topics: int = 5,
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate research topics and information relevant to the book.
        
        Args:
            book_idea: Dictionary containing the book idea
            world_data: Optional dictionary with world building data
            num_topics: Number of research topics to generate
            complexity: Complexity level (low, medium, high)
            
        Returns:
            Dictionary with generated research topics and information
        """
        logger.info(f"Generating {num_topics} research topics for project {self.project_id}")
        
        # Extract key information from book idea
        title = book_idea.get("title", "")
        genre = book_idea.get("genre", "")
        themes = book_idea.get("themes", [])
        themes_str = ", ".join(themes) if isinstance(themes, list) else themes
        plot_summary = book_idea.get("plot_summary", "")
        
        # Extract world data if available
        world_summary = ""
        if world_data:
            world_type = world_data.get("world_type", "")
            setting = world_data.get("primary_setting", "")
            time_period = world_data.get("time_period", "")
            
            world_summary = f"World Type: {world_type}\nPrimary Setting: {setting}\nTime Period: {time_period}"
        
        # Build the system prompt
        system_prompt = """You are an expert research specialist for authors, focusing on identifying and developing key topics 
that require research for a fiction or non-fiction book project.
Your task is to identify important topics that would benefit from detailed research to make the book authentic and compelling.
For each topic, provide key areas of focus, essential questions, and preliminary information.
Provide output in JSON format according to the provided schema."""
        
        # Build the user prompt
        user_prompt = f"""Identify {num_topics} critical research topics for a book with the following details:

Title: {title}
Genre: {genre}
Themes: {themes_str}
Plot Summary: {plot_summary}
{world_summary}

The research should have {complexity} complexity level of depth.
For each topic:
1. Provide a clear name and description
2. Explain why this research is important for the book
3. List key questions that need to be answered
4. Include preliminary information that would be known without specialized research
5. Suggest potential sources or research methods

Topics should cover different aspects needed to write the book authentically, such as historical periods, scientific concepts, cultural practices, professions, locations, or other relevant areas.

Respond with research topics formatted according to this JSON schema: {json.dumps(RESEARCH_SCHEMA)}
"""
        
        try:
            # Try OpenAI if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7,
                        max_tokens=3000
                    )
                    
                    research = response["parsed_json"]
                    logger.info(f"Generated {len(research.get('topics', []))} research topics using OpenAI")
                    
                    # Store in memory
                    self._store_in_memory(research)
                    
                    return research
                except Exception as e:
                    logger.warning(f"OpenAI research generation failed: {e}, using fallback research")
            
            # If we get here, OpenAI failed or isn't available
            # Generate fallback research based on the book idea
            fallback_research = self._generate_fallback_research(book_idea, world_data, num_topics)
            logger.warning("Using fallback research generation due to API failures")
            
            # Store in memory
            self._store_in_memory(fallback_research)
            
            return fallback_research
            
        except Exception as e:
            logger.error(f"Research generation error: {e}")
            # Generate fallback research as a last resort
            fallback_research = self._generate_fallback_research(book_idea, world_data, num_topics)
            
            # Store in memory
            self._store_in_memory(fallback_research)
            
            return fallback_research
    
    def _generate_fallback_research(
        self, 
        book_idea: Dict[str, Any], 
        world_data: Optional[Dict[str, Any]] = None,
        num_topics: int = 3
    ) -> Dict[str, Any]:
        """
        Generate fallback research topics when API calls fail.
        
        Args:
            book_idea: Dictionary containing the book idea
            world_data: Optional dictionary with world building data
            num_topics: Number of fallback topics to generate
            
        Returns:
            Dictionary with generated fallback research topics
        """
        genre = book_idea.get("genre", "fiction").lower()
        title = book_idea.get("title", "Untitled")
        themes = book_idea.get("themes", [])
        
        # Default topics based on genre
        default_topics = []
        
        if "fantasy" in genre:
            default_topics = [
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Magic Systems",
                    "description": "Research on how magic works in fantasy worlds",
                    "importance": "Critical for establishing consistent rules in a fantasy setting",
                    "key_questions": [
                        "How does magic work in this world?",
                        "What are its limitations?",
                        "Who can use magic and how is it learned?"
                    ],
                    "preliminary_info": "Fantasy worlds typically establish clear rules for magic to maintain internal consistency",
                    "potential_sources": ["Fantasy worldbuilding guides", "Analysis of popular fantasy magic systems"],
                    "priority": 1
                },
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Medieval Warfare",
                    "description": "Historical combat methods and strategies",
                    "importance": "Adds authenticity to battle scenes",
                    "key_questions": [
                        "How did medieval armies organize?",
                        "What weapons and armor were used?",
                        "What were common battle tactics?"
                    ],
                    "preliminary_info": "Medieval combat involved various weapon types and formation-based tactics",
                    "potential_sources": ["Military history books", "Medieval weapon encyclopedias"],
                    "priority": 2
                }
            ]
        elif "sci-fi" in genre or "science fiction" in genre:
            default_topics = [
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Future Technology",
                    "description": "Speculative technologies based on current scientific trends",
                    "importance": "Creates plausible sci-fi elements",
                    "key_questions": [
                        "What technologies might evolve from current science?",
                        "How would these technologies affect society?",
                        "What are the limitations and drawbacks?"
                    ],
                    "preliminary_info": "Future tech often extrapolates from current scientific advances",
                    "potential_sources": ["Scientific journals", "Technology forecasting reports"],
                    "priority": 1
                },
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Space Travel",
                    "description": "Mechanics and challenges of interstellar travel",
                    "importance": "Essential for realistic space-based sci-fi",
                    "key_questions": [
                        "How might faster-than-light travel work?",
                        "What are the physiological effects of long-term space travel?",
                        "What resources are needed for space journeys?"
                    ],
                    "preliminary_info": "Space travel faces challenges like radiation, resource management, and time dilation",
                    "potential_sources": ["NASA publications", "Astrophysics texts"],
                    "priority": 2
                }
            ]
        elif "historical" in genre:
            default_topics = [
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Period-Appropriate Language",
                    "description": "Speech patterns and vocabulary from the time period",
                    "importance": "Creates authentic dialogue and narration",
                    "key_questions": [
                        "How did people speak in this era?",
                        "What slang or specialized vocabulary existed?",
                        "How did communication differ between social classes?"
                    ],
                    "preliminary_info": "Historical language patterns differ significantly from modern speech",
                    "potential_sources": ["Historical linguistics resources", "Primary texts from the era"],
                    "priority": 1
                },
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Daily Life Routines",
                    "description": "Everyday activities and customs of the time period",
                    "importance": "Adds historical authenticity to character actions",
                    "key_questions": [
                        "What was a typical daily schedule?",
                        "How did people handle basic necessities?",
                        "What social customs governed interactions?"
                    ],
                    "preliminary_info": "Daily routines were heavily influenced by technology levels and social structures",
                    "potential_sources": ["Social history books", "Museum exhibits"],
                    "priority": 2
                }
            ]
        else:
            # Generic topics for any genre
            default_topics = [
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Psychology of Characters",
                    "description": "Understanding character motivations and behaviors",
                    "importance": "Creates believable character development",
                    "key_questions": [
                        "What psychological traits drive the main characters?",
                        "How do past traumas affect present behaviors?",
                        "What defense mechanisms do characters employ?"
                    ],
                    "preliminary_info": "Character psychology should be consistent and drive plot development",
                    "potential_sources": ["Psychology textbooks", "Character development guides"],
                    "priority": 1
                },
                {
                    "id": f"topic_{len(default_topics) + 1}",
                    "name": "Setting Research",
                    "description": "Details about the physical environment of the story",
                    "importance": "Creates an immersive world for readers",
                    "key_questions": [
                        "What are the key geographical features?",
                        "How does the environment affect daily life?",
                        "What sensory details define this place?"
                    ],
                    "preliminary_info": "Settings should engage multiple senses and affect character actions",
                    "potential_sources": ["Travel guides", "Maps and geographical resources"],
                    "priority": 2
                }
            ]
        
        # Add a theme-based topic if themes exist
        if themes and isinstance(themes, list) and len(themes) > 0:
            theme = themes[0] if isinstance(themes[0], str) else "general themes"
            theme_topic = {
                "id": f"topic_{len(default_topics) + 1}",
                "name": f"Exploring the Theme of {theme.capitalize()}",
                "description": f"Research on the theme of {theme} and its manifestations",
                "importance": "Strengthens thematic elements in the story",
                "key_questions": [
                    f"How has the theme of {theme} been explored in literature?",
                    f"What are common symbols associated with {theme}?",
                    f"How can {theme} be shown through character development?"
                ],
                "preliminary_info": f"The theme of {theme} can be explored through character arcs, symbolism, and plot development",
                "potential_sources": ["Literary analysis", "Philosophical texts"],
                "priority": 3
            }
            default_topics.append(theme_topic)
        
        # Limit to requested number of topics
        default_topics = default_topics[:min(num_topics, len(default_topics))]
        
        # If we don't have enough topics, add a generic one
        while len(default_topics) < num_topics:
            generic_topic = {
                "id": f"topic_{len(default_topics) + 1}",
                "name": f"Additional Research for {title}",
                "description": "General background research for the story",
                "importance": "Provides context and detail for the narrative",
                "key_questions": [
                    "What background elements need more exploration?",
                    "What details would make the story more authentic?",
                    "What information would help with worldbuilding?"
                ],
                "preliminary_info": "General research helps fill gaps in world knowledge",
                "potential_sources": ["Subject encyclopedias", "Online research"],
                "priority": len(default_topics) + 1
            }
            default_topics.append(generic_topic)
        
        # Create the complete research structure
        fallback_research = {
            "topics": default_topics,
            "general_notes": f"Fallback research generated for {title}"
        }
        
        return fallback_research
    
    def research_topic(
        self,
        topic_id: str,
        specific_questions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Research a specific topic in depth based on the topic ID.
        
        Args:
            topic_id: ID of the topic to research
            specific_questions: Optional list of specific questions to focus on
            
        Returns:
            Dictionary with detailed research on the topic
        """
        logger.info(f"Researching topic {topic_id} for project {self.project_id}")
        
        # Get the original topic from memory
        topics = self.get_all_research()
        original_topic = None
        
        for topic in topics.get("topics", []):
            if topic.get("id") == topic_id:
                original_topic = topic
                break
        
        if not original_topic:
            logger.warning(f"Topic {topic_id} not found in memory, cannot research")
            return {
                "topic_id": topic_id,
                "status": "error",
                "message": "Topic not found in memory"
            }
        
        topic_name = original_topic.get("name", "Unknown Topic")
        description = original_topic.get("description", "")
        
        # Determine questions to research
        questions = []
        if specific_questions and isinstance(specific_questions, list):
            questions.extend(specific_questions)
        
        if "key_questions" in original_topic and isinstance(original_topic["key_questions"], list):
            for q in original_topic["key_questions"]:
                if q not in questions:
                    questions.append(q)
        
        if not questions:
            questions = [
                f"What is {topic_name} and why is it important?",
                f"What are the key aspects of {topic_name} relevant to this book?",
                "What historical context is important to understand?",
                "What are common misconceptions about this topic?",
                "How has this topic evolved over time?"
            ]
        
        # Build the system prompt
        system_prompt = """You are an expert research assistant for authors.
Your task is to provide detailed, accurate research on a specific topic relevant to a book being written.
The research should be useful for an author to authentically incorporate the topic into their writing.
Focus on providing factual information, historical context, practical details, and correcting common misconceptions.
Your response must be formatted as valid JSON according to the schema provided."""
        
        # Build the user prompt
        questions_text = "\n".join([f"- {q}" for q in questions])
        user_prompt = f"""Provide detailed research on the following topic for a book:

Topic Name: {topic_name}
Description: {description}

Please answer these specific questions about the topic:
{questions_text}

For each question:
1. Provide a comprehensive answer with factual information
2. Include historical context where relevant
3. Mention practical details that would add authenticity to the writing
4. Address common misconceptions
5. Note any areas where further specialized research might be needed

Format your response as a valid JSON object with the following structure:
{{
  "topic_id": "{topic_id}",
  "topic_name": "{topic_name}",
  "research_date": "current date",
  "overall_summary": "A concise summary of your findings",
  "answers": [
    {{
      "question": "The first question",
      "answer": "Detailed response to the question",
      "key_facts": ["Important fact 1", "Important fact 2"]
    }},
    ...
  ],
  "additional_insights": ["Any other important information discovered"],
  "sources": ["Mention types of sources this information would come from"]
}}
"""
        
        try:
            # Try OpenAI if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.6,
                        max_tokens=3000
                    )
                    
                    research_results = response["parsed_json"]
                    logger.info(f"Researched topic {topic_id} using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(research_results),
                        self.name,
                        metadata={"type": "detailed_research", "topic_id": topic_id}
                    )
                    
                    return research_results
                except Exception as e:
                    logger.warning(f"OpenAI topic research failed: {e}, using fallback")
            
            # If OpenAI failed or is not enabled, use fallback
            return self._generate_fallback_topic_research(original_topic, questions)
            
        except Exception as e:
            logger.error(f"Topic research error: {e}")
            return self._generate_fallback_topic_research(original_topic, questions)
    
    def synthesize_research(self) -> Dict[str, Any]:
        """
        Synthesize all research topics into a cohesive summary.
        
        Returns:
            Dictionary with synthesized research
        """
        logger.info(f"Synthesizing research for project {self.project_id}")
        
        # Get all research topics from memory
        topics_data = self.get_all_research()
        topics = topics_data.get("topics", [])
        
        if not topics:
            logger.warning("No research topics found to synthesize")
            return {
                "status": "error",
                "message": "No research topics found to synthesize"
            }
        
        # Create a list of topic summaries
        topic_summaries = []
        for topic in topics:
            topic_name = topic.get("name", "Unknown Topic")
            description = topic.get("description", "")
            
            # Try to get detailed research for this topic
            detailed_research = None
            try:
                documents = self.memory.search(
                    query=f"detailed research on {topic_name}",
                    collection=self.name,
                    filter={"type": "detailed_research", "topic_id": topic.get("id")}
                )
                
                if documents:
                    detailed_research = json.loads(documents[0].content)
            except Exception as e:
                logger.warning(f"Error retrieving detailed research for {topic_name}: {e}")
            
            summary = f"Topic: {topic_name}\nDescription: {description}\n"
            
            if detailed_research and "overall_summary" in detailed_research:
                summary += f"Research Summary: {detailed_research['overall_summary']}\n"
                
                if "key_facts" in detailed_research:
                    key_facts = "\n".join([f"- {fact}" for fact in detailed_research["key_facts"]])
                    summary += f"Key Facts:\n{key_facts}\n"
            
            topic_summaries.append(summary)
        
        # Build the system prompt
        system_prompt = """You are an expert research synthesis specialist for authors.
Your task is to synthesize various research topics into a cohesive summary that will inform the author's writing.
Identify connections between topics, highlight the most important information, and organize the research in a way that will be most useful for writing the book.
Format your response as valid JSON according to the schema provided."""
        
        # Build the user prompt
        all_summaries = "\n\n".join(topic_summaries)
        user_prompt = f"""Synthesize the following research topics into a cohesive summary for the author:

{all_summaries}

Create a synthesis that:
1. Identifies connections between the different research topics
2. Highlights the most important information for writing the book
3. Organizes the research in a logical way
4. Notes any inconsistencies or gaps that might need further research
5. Provides recommendations for how to use this research in writing

Format your response as a valid JSON object with the following structure:
{{
  "synthesis_date": "current date",
  "overview": "A concise overview of all the research",
  "key_insights": [
    "Important insight 1",
    "Important insight 2"
  ],
  "topic_connections": [
    {{
      "topics": ["Topic A", "Topic B"],
      "connection": "Description of how these topics are connected"
    }}
  ],
  "writing_recommendations": [
    "Recommendation 1",
    "Recommendation 2"
  ],
  "gaps_and_inconsistencies": [
    "Gap 1",
    "Inconsistency 1"
  ]
}}
"""

        try:
            # Try OpenAI if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.6,
                        max_tokens=3000
                    )
                    
                    synthesis = response["parsed_json"]
                    logger.info(f"Synthesized research using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(synthesis),
                        self.name,
                        metadata={"type": "research_synthesis"}
                    )
                    
                    return synthesis
                except Exception as e:
                    logger.warning(f"OpenAI research synthesis failed: {e}, using fallback synthesis")
            
            # If OpenAI failed or is not enabled, use fallback
            return self._generate_fallback_synthesis(topics)
            
        except Exception as e:
            logger.error(f"Research synthesis error: {e}")
            return self._generate_fallback_synthesis(topics)
    
    def _generate_fallback_topic_research(
        self,
        topic: Dict[str, Any],
        questions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate fallback research for a topic when API calls fail.
        
        Args:
            topic: Dictionary containing the topic data
            questions: List of research questions
            
        Returns:
            Dictionary with fallback research results
        """
        if not questions:
            questions = topic.get("key_questions", ["What essential information is needed?"])
            if not questions:
                questions = ["What essential information is needed?"]
        
        topic_id = topic.get("id", "fallback_topic")
        topic_name = topic.get("name", "Research Topic")
        
        answers = []
        for question in questions:
            answer = {
                "question": question,
                "answer": f"This would contain detailed information about {topic_name} relevant to the question. Since this is fallback content, the author should research this topic further.",
                "sources": ["Author's research", "Subject matter references"]
            }
            answers.append(answer)
        
        research_results = {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "research_date": datetime.now().strftime("%Y-%m-%d"),
            "answers": answers,
            "additional_findings": [f"Consider how {topic_name} influences character development"],
            "connections": ["May connect to other story elements"]
        }
        
        # Store in memory
        self.memory.add_document(
            json.dumps(research_results),
            self.name,
            metadata={"type": "detailed_research", "topic_id": topic_id}
        )
        
        logger.warning(f"Using fallback research for topic {topic_id}")
        return research_results
    
    def _generate_fallback_synthesis(self, topics: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate fallback research synthesis when API calls fail.
        
        Args:
            topics: List of research topics if available
            
        Returns:
            Dictionary with fallback synthesis
        """
        # Create topic names for key findings
        key_findings = []
        if topics and len(topics) > 0:
            # Use actual topics if available
            for topic in topics[:3]:
                topic_name = topic.get('name', 'Research Topic')
                key_finding = {
                    "topic": topic_name,
                    "critical_points": [
                        f"Consider how {topic_name} influences the story",
                        f"Integrate {topic_name} into character backgrounds"
                    ]
                }
                key_findings.append(key_finding)
        else:
            # Generic key findings if no topics
            key_findings = [
                {
                    "topic": "Setting Research",
                    "critical_points": [
                        "Develop detailed environmental descriptions",
                        "Consider how setting influences character actions"
                    ]
                },
                {
                    "topic": "Character Backgrounds",
                    "critical_points": [
                        "Research relevant professions or skills",
                        "Consider psychological motivations"
                    ]
                }
            ]
        
        # Create a basic synthesis
        synthesis = {
            "overview": "This research provides background information to enhance the authenticity of the story.",
            "key_findings": key_findings,
            "connections": [
                {
                    "description": "Setting elements can influence character development",
                    "related_topics": ["Setting", "Characters"],
                    "significance": "Creates a cohesive relationship between characters and their environment"
                }
            ],
            "writing_recommendations": [
                "Incorporate research details naturally without info-dumping",
                "Prioritize character development over excessive world details",
                "Use research to add authenticity rather than to showcase knowledge"
            ],
            "research_gaps": [
                "Consider researching more about specific character professions",
                "More detailed setting information may enhance immersion"
            ]
        }
        
        # Store in memory
        self.memory.add_document(
            json.dumps(synthesis),
            self.name,
            metadata={"type": "research_synthesis"}
        )
        
        logger.warning("Using fallback research synthesis")
        return synthesis
    
    def _store_in_memory(self, research: Dict[str, Any]) -> None:
        """
        Store generated research in memory.
        
        Args:
            research: Dictionary with generated research topics
        """
        if "topics" not in research or not isinstance(research["topics"], list):
            logger.warning("Invalid research format for memory storage")
            return
        
        # Store the entire research dict
        self.memory.add_document(
            json.dumps(research),
            self.name,
            metadata={"type": "research_results"}
        )
        
        # Store each individual topic for easier retrieval
        for topic in research["topics"]:
            topic_id = topic.get("id")
            if not topic_id:
                continue
                
            self.memory.add_document(
                json.dumps(topic),
                self.name,
                metadata={"type": "topic", "topic_id": topic_id}
            )
    
    def get_all_research(self) -> Dict[str, Any]:
        """
        Get all research from memory.
        
        Returns:
            Dictionary with compiled research data
        """
        # Query for all research in memory
        research_docs = self.memory.get_agent_memory(self.name)
        
        if not research_docs:
            raise ValueError("No research found in memory")
        
        # Initialize result structure
        result = {
            "topics": [],
            "detailed_research": [],
            "synthesis": None
        }
        
        # Process each document
        for doc in research_docs:
            metadata = doc.get('metadata', {})
            doc_type = metadata.get('type', '')
            
            try:
                data = json.loads(doc['text'])
                
                if doc_type == 'topic':
                    result["topics"].append(data)
                elif doc_type == 'detailed_research':
                    result["detailed_research"].append(data)
                elif doc_type == 'research_synthesis':
                    result["synthesis"] = data
                elif doc_type == 'research_results' and 'topics' in data:
                    # Add any topics not already in the list
                    existing_ids = {t.get('id') for t in result["topics"] if 'id' in t}
                    new_topics = [t for t in data['topics'] if t.get('id') not in existing_ids]
                    result["topics"].extend(new_topics)
            except json.JSONDecodeError:
                continue
        
        # Filter duplicates in topics by ID
        if result["topics"]:
            unique_topics = {}
            for topic in result["topics"]:
                topic_id = topic.get('id')
                if topic_id:
                    unique_topics[topic_id] = topic
            
            result["topics"] = list(unique_topics.values())
        
        return result
