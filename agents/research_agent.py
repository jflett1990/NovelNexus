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
            # Try OpenAI first if enabled
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
                    logger.warning(f"OpenAI research generation failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                try:
                    response = self.ollama_client.generate(
                        prompt=user_prompt,
                        system=system_prompt,
                        format="json"
                    )
                    
                    # Extract and parse JSON from response
                    text_response = response.get("response", "{}")
                    
                    # Extracting the JSON part from the response
                    json_start = text_response.find("{")
                    json_end = text_response.rfind("}") + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = text_response[json_start:json_end]
                        research = json.loads(json_str)
                    else:
                        raise ValueError("Could not extract valid JSON from Ollama response")
                    
                    logger.info(f"Generated {len(research.get('topics', []))} research topics using Ollama")
                    
                    # Store in memory
                    self._store_in_memory(research)
                    
                    return research
                except Exception as e:
                    logger.warning(f"Ollama research generation failed: {e}, using fallback research")
            
            # If we get here, both API calls failed or aren't available
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
        Research a specific topic in more depth.
        
        Args:
            topic_id: ID of the topic to research
            specific_questions: Optional list of specific questions to answer
            
        Returns:
            Dictionary with detailed research information
        """
        # Try to retrieve the original topic from memory
        try:
            original_topics = self.memory.query_memory(f"topic_id:{topic_id}", agent_name=self.name)
            
            if not original_topics:
                logger.warning(f"Topic with ID {topic_id} not found in memory, trying alternative queries")
                # Try alternative queries
                all_topics = self.memory.query_memory("type:topic", agent_name=self.name)
                if all_topics:
                    logger.info(f"Found {len(all_topics)} topics, using the first available one")
                    original_topics = [all_topics[0]]
                else:
                    logger.warning("No topics found at all, using fallback topic")
                    # Create a fallback topic
                    fallback_topic = {
                        "id": topic_id,
                        "name": "General Research",
                        "description": "General background information",
                        "key_questions": ["What background information is relevant?", 
                                        "What details would enhance the narrative?"]
                    }
                    return self._generate_fallback_topic_research(fallback_topic, specific_questions)
            
            original_topic_doc = original_topics[0]
            original_topic_text = original_topic_doc['text']
            
            try:
                original_topic = json.loads(original_topic_text)
            except json.JSONDecodeError:
                logger.warning(f"Invalid topic data for ID {topic_id}, using fallback")
                fallback_topic = {
                    "id": topic_id,
                    "name": "Research Topic",
                    "description": "Important background information",
                    "key_questions": ["What information is needed for this story?"]
                }
                return self._generate_fallback_topic_research(fallback_topic, specific_questions)
            
            # Build questions to research
            questions = specific_questions or original_topic.get("key_questions", [])
            
            if not questions:
                questions = ["What essential information would help develop this story?"]
                logger.warning("No questions provided for research, using default question")
            
            questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
            
            # Build the system prompt
            system_prompt = """You are an expert researcher capable of providing detailed, accurate, and well-structured information on specific topics.
Your task is to answer research questions in depth, providing factual information that would help an author write authentically about this topic.
Include relevant details, historical context, technical information, and cultural nuances as appropriate.
For fictional worlds, use your knowledge to provide plausible extrapolations.
Provide output in JSON format."""
            
            # Build the user prompt
            user_prompt = f"""Research the following topic in depth: {original_topic.get('name', 'Unknown Topic')}

Topic description: {original_topic.get('description', '')}

Please answer these specific questions:
{questions_text}

Provide comprehensive, well-structured answers with relevant facts, concepts, and details an author would need.
Each answer should be thorough enough to serve as a reference when writing about this topic.

Respond with research results formatted as a JSON object in this format:
{{
  "topic_id": "{topic_id}",
  "topic_name": "{original_topic.get('name', 'Unknown Topic')}",
  "research_date": "current date",
  "answers": [
    {{
      "question": "Question text",
      "answer": "Detailed answer with multiple paragraphs and specific information",
      "sources": ["Potential sources for this information", "Another potential source"]
    }}
  ],
  "additional_findings": ["Any unexpected but relevant discoveries"],
  "connections": ["Connections to other topics or aspects of the book"]
}}
"""
            
            try:
                # Try OpenAI first if enabled
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
                        logger.warning(f"OpenAI topic research failed: {e}, falling back to Ollama")
                
                # Fall back to Ollama if OpenAI failed or is not enabled
                if self.use_ollama and self.ollama_client:
                    try:
                        response = self.ollama_client.generate(
                            prompt=user_prompt,
                            system=system_prompt,
                            format="json"
                        )
                        
                        # Extract and parse JSON from response
                        text_response = response.get("response", "{}")
                        
                        # Extracting the JSON part from the response
                        json_start = text_response.find("{")
                        json_end = text_response.rfind("}") + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = text_response[json_start:json_end]
                            research_results = json.loads(json_str)
                        else:
                            raise ValueError("Could not extract valid JSON from Ollama response")
                        
                        logger.info(f"Researched topic {topic_id} using Ollama")
                        
                        # Store in memory
                        self.memory.add_document(
                            json.dumps(research_results),
                            self.name,
                            metadata={"type": "detailed_research", "topic_id": topic_id}
                        )
                        
                        return research_results
                    except Exception as e:
                        logger.warning(f"Ollama topic research failed: {e}, using fallback")
                
                # If both API calls failed, use fallback
                return self._generate_fallback_topic_research(original_topic, questions)
                
            except Exception as e:
                logger.error(f"Topic research error: {e}")
                return self._generate_fallback_topic_research(original_topic, questions)
                
        except Exception as e:
            logger.error(f"Error in research_topic method: {e}")
            fallback_topic = {
                "id": topic_id,
                "name": "Research Topic",
                "description": "Important background information",
                "key_questions": ["What essential information is needed?"]
            }
            return self._generate_fallback_topic_research(fallback_topic, specific_questions)

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
    
    def synthesize_research(self) -> Dict[str, Any]:
        """
        Synthesize all research topics into a cohesive summary.
        
        Returns:
            Dictionary with synthesized research
        """
        # Retrieve all research from memory
        try:
            research_docs = self.memory.get_agent_memory(self.name)
            
            if not research_docs:
                logger.warning("No research found in memory, generating minimal synthesis")
                return self._generate_fallback_synthesis()
            
            # Extract topics and detailed research
            topics = []
            detailed_research = []
            
            for doc in research_docs:
                metadata = doc.get('metadata', {})
                doc_type = metadata.get('type', '')
                
                try:
                    data = json.loads(doc['text'])
                    
                    if doc_type == 'topic':
                        topics.append(data)
                    elif doc_type == 'detailed_research':
                        detailed_research.append(data)
                    elif doc_type == 'research_results' and 'topics' in data:
                        topics.extend(data['topics'])
                except json.JSONDecodeError:
                    continue
            
            if not topics:
                logger.warning("No valid research topics found in memory, generating minimal synthesis")
                return self._generate_fallback_synthesis()
            
            # Build the system prompt
            system_prompt = """You are an expert research synthesizer for authors.
Your task is to analyze multiple research topics and findings, identify connections between them,
and create a cohesive summary that highlights the most important elements for the book project.
Focus on creating a useful reference that connects different research areas.
Provide output in JSON format."""
            
            # Build the user prompt
            topic_summaries = []
            for topic in topics[:3]:  # Limit to prevent excessive prompt length
                topic_name = topic.get('name', 'Unknown Topic')
                topic_desc = topic.get('description', '')
                topic_importance = topic.get('importance', '')
                
                summary = f"Topic: {topic_name}\nDescription: {topic_desc}\nImportance: {topic_importance}"
                topic_summaries.append(summary)
            
            detailed_summaries = []
            for research in detailed_research[:2]:  # Limit to prevent excessive prompt length
                topic_name = research.get('topic_name', 'Unknown Topic')
                answers = research.get('answers', [])
                
                answer_texts = [f"Q: {a.get('question', '')}\nA: {a.get('answer', '')[:200]}..." for a in answers[:2]]
                answer_summary = "\n".join(answer_texts)
                
                summary = f"Detailed Research - {topic_name}:\n{answer_summary}"
                detailed_summaries.append(summary)
            
            topics_text = "\n\n".join(topic_summaries)
            detailed_text = "\n\n".join(detailed_summaries)
            
            user_prompt = f"""Synthesize the following research topics and detailed findings into a cohesive summary for an author:

RESEARCH TOPICS:
{topics_text}

DETAILED RESEARCH:
{detailed_text}

Create a synthesis that:
1. Summarizes the key findings across all topics
2. Identifies important connections between different research areas
3. Highlights the most critical information for writing the book
4. Organizes the information in a useful, accessible structure
5. Notes any gaps that might need additional research

Respond with the synthesis formatted as a JSON object in this format:
{{
  "overview": "Executive summary of all research",
  "key_findings": [
    {{
      "topic": "Topic name",
      "critical_points": ["Important point 1", "Important point 2"]
    }}
  ],
  "connections": [
    {{
      "description": "Description of a connection between topics",
      "related_topics": ["Topic 1", "Topic 2"],
      "significance": "Why this connection matters for the book"
    }}
  ],
  "writing_recommendations": ["Specific recommendations for using this research in writing"],
  "research_gaps": ["Areas that might need additional research"]
}}
"""
            
            try:
                # Try OpenAI first if enabled
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
                        logger.warning(f"OpenAI research synthesis failed: {e}, falling back to Ollama")
                
                # Fall back to Ollama if OpenAI failed or is not enabled
                if self.use_ollama and self.ollama_client:
                    try:
                        response = self.ollama_client.generate(
                            prompt=user_prompt,
                            system=system_prompt,
                            format="json"
                        )
                        
                        # Extract and parse JSON from response
                        text_response = response.get("response", "{}")
                        
                        # Extracting the JSON part from the response
                        json_start = text_response.find("{")
                        json_end = text_response.rfind("}") + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = text_response[json_start:json_end]
                            synthesis = json.loads(json_str)
                        else:
                            raise ValueError("Could not extract valid JSON from Ollama response")
                        
                        logger.info(f"Synthesized research using Ollama")
                        
                        # Store in memory
                        self.memory.add_document(
                            json.dumps(synthesis),
                            self.name,
                            metadata={"type": "research_synthesis"}
                        )
                        
                        return synthesis
                    except Exception as e:
                        logger.warning(f"Ollama research synthesis failed: {e}, using fallback synthesis")
                
                # If both API calls failed, use fallback
                return self._generate_fallback_synthesis(topics)
                
            except Exception as e:
                logger.error(f"Research synthesis error: {e}")
                return self._generate_fallback_synthesis(topics)
                
        except Exception as e:
            logger.error(f"Error in synthesize_research method: {e}")
            return self._generate_fallback_synthesis()
    
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
