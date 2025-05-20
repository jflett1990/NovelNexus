import logging
import json
from typing import Dict, Any, List, Optional
import re


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.review_schema import REVIEW_SCHEMA

logger = logging.getLogger(__name__)

class ReviewAgent:
    """
    Agent responsible for reviewing and critiquing the written content.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Review Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "review_agent"
        self.stage = "review"
    
    def review_chapter(
        self,
        chapter_data: Dict[str, Any],
        chapter_outline: Dict[str, Any],
        style_guide: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Review a written chapter against its outline and style guidelines.
        
        Args:
            chapter_data: Dictionary containing the written chapter
            chapter_outline: Dictionary containing the chapter outline
            style_guide: Optional style guide for evaluating style consistency
            
        Returns:
            Dictionary with review results
        """
        logger.info(f"Reviewing chapter {chapter_data.get('id', 'unknown')} for project {self.project_id}")
        
        # Ensure chapter_data is a dictionary, not a string
        if isinstance(chapter_data, str):
            try:
                chapter_data = json.loads(chapter_data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse chapter_data as JSON, creating minimal structure")
                chapter_data = {
                    "id": "unknown",
                    "title": "Untitled Chapter",
                    "content": chapter_data[:10000] if len(chapter_data) > 10000 else chapter_data
                }
        
        # Ensure chapter_outline is a dictionary, not a string
        if isinstance(chapter_outline, str):
            try:
                chapter_outline = json.loads(chapter_outline)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse chapter_outline as JSON, creating minimal structure")
                chapter_outline = {
                    "id": "unknown",
                    "title": "Untitled Chapter",
                    "summary": chapter_outline[:500] if len(chapter_outline) > 500 else chapter_outline
                }
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_content = chapter_data.get("content", "")
        
        # Extract key information from chapter outline
        outline_summary = chapter_outline.get("summary", "")
        outline_scenes = chapter_outline.get("scenes", [])
        outline_featured_characters = chapter_outline.get("featured_characters", [])
        
        # Extract style guide information if available
        style_text = ""
        if style_guide:
            if isinstance(style_guide, str):
                try:
                    style_guide = json.loads(style_guide)
                except json.JSONDecodeError:
                    style_text = style_guide
            else:
                style_text = json.dumps(style_guide, indent=2)
        
        # Build the system prompt
        system_prompt = """You are an expert literary editor and critic with a keen eye for narrative structure, character development, pacing, and prose quality.
Your task is to conduct a thorough review of a book chapter, evaluating how well it meets its outlined goals and adheres to style guidelines.
Provide detailed, constructive feedback with specific examples and actionable recommendations for improvement.
Your review should be balanced, noting both strengths and areas for improvement.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Review Chapter {chapter_number}: {chapter_title} against its outline and style guidelines:

Chapter Content:
{chapter_content[:10000]}  # Limit content to avoid token limits

Chapter Outline:
{outline_summary}

{"Key Scenes from Outline:" if outline_scenes else ""}
{json.dumps(outline_scenes, indent=2) if outline_scenes else ""}

{"Featured Characters from Outline:" if outline_featured_characters else ""}
{', '.join(outline_featured_characters) if outline_featured_characters else ""}

{"Style Guidelines:" if style_text else ""}
{style_text}

Conduct a thorough review addressing:
1. Plot & Structure: Does the chapter follow the outlined plot points? Is the narrative structure effective?
2. Character Development: Are the characters portrayed consistently and developed effectively?
3. Setting & Atmosphere: Is the setting vividly portrayed and appropriate to the story?
4. Dialogue: Is the dialogue natural, purposeful, and true to each character's voice?
5. Pacing & Flow: Does the chapter maintain appropriate pacing? Are transitions smooth?
6. Prose Quality: Is the writing engaging, clear, and effective?
7. Style Consistency: Does the writing adhere to the style guidelines?
8. Overall Assessment: What are the chapter's strengths and weaknesses?

For each issue identified, provide:
- A specific example from the text
- An explanation of why it's problematic
- A practical suggestion for improvement

Respond with the review formatted as a JSON object with the following properties:
- overall_rating: a number from 1-10
- strengths: an array of strings describing chapter strengths
- issues: an array of objects with {{"description", "severity", "example", "suggestion"}} 
- recommendations: an array of strings with major revision suggestions
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
                    
                    review = response["parsed_json"]
                    logger.info(f"Reviewed chapter {chapter_id} using OpenAI")
                    
                    # Store in memory
                    self._store_in_memory(review, chapter_id)
                    
                    return review
                except Exception as e:
                    logger.warning(f"OpenAI chapter review failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    format="json"
                )
                
                # Extract and parse JSON from response
                text_response = response.get("response", "{}")
                
                try:
                    # First try to parse the entire response as JSON
                    review = json.loads(text_response)
                except json.JSONDecodeError:
                    # If that fails, try to extract JSON using regex
                    logger.warning(f"Failed to parse Ollama response as JSON, attempting to extract valid JSON")
                    
                    # Extracting the JSON part from the response
                    json_start = text_response.find("{")
                    json_end = text_response.rfind("}") + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = text_response[json_start:json_end]
                        try:
                            review = json.loads(json_str)
                        except json.JSONDecodeError as json_error:
                            logger.error(f"Failed to extract JSON from Ollama response: {json_error}")
                            # Create a fallback review structure
                            review = {
                                "overall_rating": 5,
                                "strengths": ["The chapter was written successfully"],
                                "issues": [{"description": "Unable to analyze due to JSON parsing error", 
                                           "severity": "medium", 
                                           "example": "N/A", 
                                           "suggestion": "Please review manually"}],
                                "recommendations": ["Review chapter manually due to AI analysis failure"]
                            }
                    else:
                        # If no valid JSON can be found, create a fallback review
                        logger.error("No valid JSON found in Ollama response")
                        review = {
                            "overall_rating": 5,
                            "strengths": ["The chapter was written successfully"],
                            "issues": [{"description": "Unable to analyze due to JSON parsing error", 
                                       "severity": "medium", 
                                       "example": "N/A", 
                                       "suggestion": "Please review manually"}],
                            "recommendations": ["Review chapter manually due to AI analysis failure"]
                        }
                
                # Validate/fix the review structure
                if not isinstance(review, dict):
                    logger.warning("Review result is not a dictionary, creating fallback")
                    review = {
                        "overall_rating": 5,
                        "strengths": ["Content was generated"],
                        "issues": [{"description": "Invalid review format", 
                                   "severity": "medium", 
                                   "example": "N/A", 
                                   "suggestion": "Please review manually"}],
                        "recommendations": ["Review chapter manually"]
                    }
                
                # Ensure required fields exist
                required_fields = ["overall_rating", "strengths", "issues", "recommendations"]
                for field in required_fields:
                    if field not in review:
                        if field == "overall_rating":
                            review[field] = 5
                        else:
                            review[field] = []
                            
                # If issues field exists but has invalid structure, fix it
                if "issues" in review and not isinstance(review["issues"], list):
                    review["issues"] = []
                
                logger.info(f"Reviewed chapter {chapter_id} using Ollama")
                
                # Store in memory
                self._store_in_memory(review, chapter_id)
                
                return review
            
            raise Exception("No available AI service (OpenAI or Ollama) to review chapter")
            
        except Exception as e:
            logger.error(f"Chapter review error: {e}")
            # Return a fallback review instead of raising an exception
            fallback_review = {
                "overall_rating": 5,
                "strengths": ["The chapter was written successfully"],
                "issues": [{"description": f"Review failed: {str(e)}", 
                           "severity": "medium", 
                           "example": "N/A", 
                           "suggestion": "Please check the chapter manually"}],
                "recommendations": ["Manual review required due to error"]
            }
            
            # Store the fallback in memory
            self._store_in_memory(fallback_review, chapter_id)
            
            return fallback_review
    
    def analyze_manuscript_consistency(self, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the consistency of a manuscript across chapters.
        
        Args:
            chapters: List of chapter data
            
        Returns:
            Dictionary with consistency analysis
        """
        if not chapters:
            logger.warning("No chapters provided for consistency analysis")
            return {
                "consistency_score": 0,
                "issues": [],
                "recommendations": ["No chapters available for analysis"]
            }
        
        # Create a consolidated prompt for consistency analysis
        chapter_summaries = []
        for i, chapter in enumerate(chapters):
            title = chapter.get("title", f"Chapter {i+1}")
            content_preview = chapter.get("content", "")
            if content_preview:
                content_preview = content_preview[:500] + "..." if len(content_preview) > 500 else content_preview
            chapter_summaries.append(f"Chapter: {title}\nPreview: {content_preview}\n")
        
        chapters_text = "\n".join(chapter_summaries)
        
        prompt = f"""
        Analyze the consistency of the following manuscript chapters:
        
        {chapters_text}
        
        Provide a detailed consistency analysis covering:
        1. Character consistency (names, traits, motivations)
        2. Plot consistency (timeline, events, cause-effect relationships)
        3. Setting consistency (locations, world rules, descriptions)
        4. Tone consistency (writing style, mood, voice)
        
        Format your response as valid JSON with the following structure:
        {{
            "consistency_score": [1-10 rating],
            "issues": [
                {{
                    "type": ["character"|"plot"|"setting"|"tone"],
                    "description": "Description of the inconsistency",
                    "location": "Chapter information",
                    "severity": ["high"|"medium"|"low"]
                }}
            ],
            "recommendations": [
                "Recommendation to fix the issue"
            ]
        }}
        
        Focus only on identifying major inconsistencies. If no significant issues are found, return an empty issues array.
        Ensure your JSON is properly formatted with no trailing commas.
        """
        
        try:
            model_response = None
            
            # First try with Ollama model if available
            if self.use_ollama:
                try:
                    model_response = self.ollama_client.generate(
                        prompt=prompt,
                        model="deepseek-v2:16b",
                        context_window=24000,
                        temperature=0.1,
                        top_p=0.1
                    )
                except Exception as e:
                    logger.error(f"Error generating consistency analysis with Ollama: {e}")
                    # Fall back to OpenAI
            
            # Try OpenAI if Ollama failed or is not available
            if not model_response and self.use_openai:
                try:
                    model_response = self.openai_client.generate(
                        prompt=prompt,
                        model="gpt-4o",
                        temperature=0.1,
                        top_p=0.1
                    )
                except Exception as e:
                    logger.error(f"Error generating consistency analysis with OpenAI: {e}")
            
            # Create a fallback if neither model worked
            if not model_response:
                logger.warning("No model response for consistency analysis, creating fallback")
                return {
                    "consistency_score": 5,
                    "issues": [],
                    "recommendations": ["Analysis unavailable due to model errors"]
                }
            
            # Extract JSON from the response - first try to parse the whole response
            try:
                result = json.loads(model_response)
                
                # Validate that the structure is correct
                if not isinstance(result, dict):
                    raise ValueError("Response is not a dictionary")
                
                if "consistency_score" not in result:
                    result["consistency_score"] = 5
                
                if "issues" not in result:
                    result["issues"] = []
                
                if "recommendations" not in result:
                    result["recommendations"] = []
                
                return result
            
            except json.JSONDecodeError:
                # Try to extract JSON using regex
                try:
                    logger.warning("Failed to parse response as JSON, trying to extract JSON with regex")
                    import re
                    
                    # Look for content between curly braces, including nested braces
                    json_pattern = r'({(?:[^{}]|(?:{[^{}]*})|(?:{{[^{}]*}})|(?:{{{[^{}]*}}})|(?:{{{{[^{}]*}}}}))*})'
                    json_matches = re.findall(json_pattern, model_response)
                    
                    if json_matches:
                        for match in json_matches:
                            try:
                                # Try parsing each match
                                result = json.loads(match)
                                logger.info("Successfully extracted JSON with regex")
                                
                                # Validate that the structure is correct
                                if not isinstance(result, dict):
                                    raise ValueError("Response is not a dictionary")
                                
                                if "consistency_score" not in result:
                                    result["consistency_score"] = 5
                                
                                if "issues" not in result:
                                    result["issues"] = []
                                
                                if "recommendations" not in result:
                                    result["recommendations"] = []
                                
                                return result
                            except json.JSONDecodeError:
                                continue
                    
                    # If we reach here, no valid JSON was found with regex
                    raise ValueError("Could not extract valid JSON from response")
                
                except Exception as e:
                    logger.error(f"Error extracting JSON with regex: {e}")
                    # Fall back to creating a minimal structure
                    return {
                        "consistency_score": 5,
                        "issues": [],
                        "recommendations": ["Analysis unavailable due to JSON parsing errors"]
                    }
            
            except Exception as e:
                logger.error(f"Error processing consistency analysis: {e}")
                return {
                    "consistency_score": 5,
                    "issues": [],
                    "recommendations": [f"Analysis error: {str(e)}"]
                }
        
        except Exception as e:
            logger.error(f"Failed to analyze manuscript consistency: {str(e)}")
            # Return fallback consistency analysis
            return {
                "consistency_score": 5,
                "issues": [],
                "recommendations": [f"Analysis could not be completed: {str(e)}"]
            }
    
    def analyze_chapter_readability(
        self,
        chapter_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze the readability and engagement level of a chapter.
        
        Args:
            chapter_data: Dictionary containing the written chapter
            
        Returns:
            Dictionary with readability analysis
        """
        logger.info(f"Analyzing readability for chapter {chapter_data.get('id', 'unknown')}")
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_content = chapter_data.get("content", "")
        
        # Calculate basic readability metrics
        word_count = len(chapter_content.split())
        sentence_count = len(re.split(r'[.!?]+', chapter_content))
        paragraph_count = len(re.split(r'\n\s*\n', chapter_content))
        
        average_sentence_length = word_count / max(1, sentence_count)
        average_paragraph_length = word_count / max(1, paragraph_count)
        
        # Build the system prompt
        system_prompt = """You are an expert in readability analysis and literary engagement.
Your task is to analyze a book chapter for readability, engagement, clarity, and narrative flow.
Provide detailed insights into what makes the writing effective or where it could be improved.
Include specific examples and actionable recommendations.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Analyze the readability and engagement of Chapter {chapter_number}: {chapter_title}:

Basic Metrics:
- Word Count: {word_count}
- Sentence Count: {sentence_count}
- Paragraph Count: {paragraph_count}
- Average Sentence Length: {average_sentence_length:.2f} words
- Average Paragraph Length: {average_paragraph_length:.2f} words

Chapter Content:
{chapter_content[:10000]}  # Limit content to avoid token limits

Analyze this chapter for:
1. Readability: How easy is it to read and comprehend? Consider sentence structure, vocabulary, and flow.
2. Engagement: How engaging is the writing? Does it hold the reader's interest?
3. Clarity: Is the writing clear and precise? Are there instances of confusion or ambiguity?
4. Pacing: Is the pacing appropriate for the content? Does it vary effectively?
5. Dialogue: Is dialogue natural and purposeful?
6. Descriptive Language: Is descriptive language vivid and effective?
7. Emotional Impact: Does the writing evoke emotional responses where appropriate?

For each area, provide:
- A rating (1-10)
- Specific examples of strengths
- Specific examples of weaknesses
- Practical suggestions for improvement

Respond with the analysis formatted as a JSON object in this format:
{{
  "chapter_id": "{chapter_id}",
  "overall_readability_score": 0-10,
  "readability_summary": "string",
  "metrics": {{
    "word_count": {word_count},
    "sentence_count": {sentence_count},
    "paragraph_count": {paragraph_count},
    "average_sentence_length": {average_sentence_length:.2f},
    "average_paragraph_length": {average_paragraph_length:.2f},
    "estimated_reading_time_minutes": 0
  }},
  "readability_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "engagement_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "clarity_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "pacing_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "dialogue_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "descriptive_language_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "emotional_impact_analysis": {{
    "score": 0-10,
    "strengths": ["string"],
    "weaknesses": ["string"],
    "suggestions": ["string"]
  }},
  "priority_recommendations": [
    {{
      "focus_area": "string",
      "recommendation": "string"
    }}
  ]
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
                        temperature=0.7,
                        max_tokens=3000
                    )
                    
                    analysis = response["parsed_json"]
                    logger.info(f"Analyzed readability for chapter {chapter_id} using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(analysis),
                        self.name,
                        metadata={"type": "readability_analysis", "chapter_id": chapter_id}
                    )
                    
                    return analysis
                except Exception as e:
                    logger.warning(f"OpenAI readability analysis failed: {e}, falling back to Ollama")
            
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
                    analysis = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Analyzed readability for chapter {chapter_id} using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(analysis),
                    self.name,
                    metadata={"type": "readability_analysis", "chapter_id": chapter_id}
                )
                
                return analysis
            
            raise Exception("No available AI service (OpenAI or Ollama) to analyze readability")
            
        except Exception as e:
            logger.error(f"Readability analysis error: {e}")
            raise Exception(f"Failed to analyze chapter readability: {e}")
    
    def _store_in_memory(self, review: Dict[str, Any], chapter_id: str) -> None:
        """
        Store review in memory.
        
        Args:
            review: Dictionary with review results
            chapter_id: ID of the reviewed chapter
        """
        # Store the review
        self.memory.add_document(
            json.dumps(review),
            self.name,
            metadata={"type": "chapter_review", "chapter_id": chapter_id}
        )
    
    def get_chapter_review(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the review for a specific chapter.
        
        Args:
            chapter_id: ID of the chapter
            
        Returns:
            Dictionary with review or None if not found
        """
        # Query for review in memory
        review_docs = self.memory.query_memory(f"chapter_id:{chapter_id}", agent_name=self.name)
        
        review_docs = [doc for doc in review_docs if doc.get('metadata', {}).get('type') == 'chapter_review']
        
        if not review_docs:
            return None
        
        try:
            return json.loads(review_docs[0]['text'])
        except (json.JSONDecodeError, IndexError):
            return None
    
    def get_all_reviews(self) -> List[Dict[str, Any]]:
        """
        Get all chapter reviews from memory.
        
        Returns:
            List of dictionaries with reviews
        """
        # Query for all reviews in memory
        review_docs = self.memory.get_agent_memory(self.name)
        
        if not review_docs:
            return []
        
        # Filter for chapter reviews
        reviews = []
        
        for doc in review_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'chapter_review':
                try:
                    review = json.loads(doc['text'])
                    reviews.append(review)
                except json.JSONDecodeError:
                    continue
        
        return reviews
