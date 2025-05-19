import logging
import json
from typing import Dict, Any, List, Optional

from models.ollama_client import get_ollama_client
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
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the Research Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
            use_ollama: Whether to use Ollama models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        self.use_ollama = use_ollama
        
        self.ollama_client = get_ollama_client() if use_ollama else None
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
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate research")
            
        except Exception as e:
            logger.error(f"Research generation error: {e}")
            raise Exception(f"Failed to generate research: {e}")
    
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
        # Retrieve the original topic from memory
        original_topics = self.memory.query_memory(f"topic_id:{topic_id}", agent_name=self.name)
        
        if not original_topics:
            raise ValueError(f"Topic with ID {topic_id} not found in memory")
        
        original_topic_doc = original_topics[0]
        original_topic_text = original_topic_doc['text']
        
        try:
            original_topic = json.loads(original_topic_text)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid topic data for ID {topic_id}")
        
        # Build questions to research
        questions = specific_questions or original_topic.get("key_questions", [])
        
        if not questions:
            raise ValueError("No questions provided for research")
        
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
            
            raise Exception("No available AI service (OpenAI or Ollama) to research topic")
            
        except Exception as e:
            logger.error(f"Topic research error: {e}")
            raise Exception(f"Failed to research topic: {e}")
    
    def synthesize_research(self) -> Dict[str, Any]:
        """
        Synthesize all research topics into a cohesive summary.
        
        Returns:
            Dictionary with synthesized research
        """
        # Retrieve all research from memory
        research_docs = self.memory.get_agent_memory(self.name)
        
        if not research_docs:
            raise ValueError("No research found in memory")
        
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
            raise ValueError("No valid research topics found in memory")
        
        # Build the system prompt
        system_prompt = """You are an expert research synthesizer for authors.
Your task is to analyze multiple research topics and findings, identify connections between them,
and create a cohesive summary that highlights the most important elements for the book project.
Focus on creating a useful reference that connects different research areas.
Provide output in JSON format."""
        
        # Build the user prompt
        topic_summaries = []
        for topic in topics:
            topic_name = topic.get('name', 'Unknown Topic')
            topic_desc = topic.get('description', '')
            topic_importance = topic.get('importance', '')
            
            summary = f"Topic: {topic_name}\nDescription: {topic_desc}\nImportance: {topic_importance}"
            topic_summaries.append(summary)
        
        detailed_summaries = []
        for research in detailed_research:
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
            
            raise Exception("No available AI service (OpenAI or Ollama) to synthesize research")
            
        except Exception as e:
            logger.error(f"Research synthesis error: {e}")
            raise Exception(f"Failed to synthesize research: {e}")
    
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
