import logging
import json
from typing import Dict, Any, List, Optional

from memory.dynamic_memory import DynamicMemory

logger = logging.getLogger(__name__)

class CentralHub:
    """
    Central integration hub for aggregating and managing data flow between agents.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory
    ):
        """
        Initialize the Central Hub.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
        """
        self.project_id = project_id
        self.memory = memory
        self.name = "central_hub"
    
    def aggregate_ideation_data(self, selected_idea_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate data from the ideation stage.
        
        Args:
            selected_idea_id: Optional ID of selected idea (if None, best idea will be used)
            
        Returns:
            Dictionary with aggregated ideation data
        """
        logger.info(f"Aggregating ideation data for project {self.project_id}")
        
        # Get ideation agent data
        ideation_docs = self.memory.query_memory("type:ideation_results", agent_name="ideation_agent")
        
        if not ideation_docs:
            logger.warning(f"No ideation_results found for project {self.project_id}, trying alternative queries")
            # Try alternative queries
            ideation_docs = self.memory.query_memory("type:idea", agent_name="ideation_agent")
            if not ideation_docs:
                logger.warning("No idea documents found either")
                # Try to get all documents from ideation agent
                ideation_docs = self.memory.get_agent_memory("ideation_agent")
                if not ideation_docs:
                    logger.error(f"No ideation agent documents found for project {self.project_id}")
                    raise ValueError("No ideation data found")
                else:
                    logger.info(f"Found {len(ideation_docs)} general documents from ideation agent")
            else:
                logger.info(f"Found {len(ideation_docs)} individual idea documents")
        else:
            logger.info(f"Found {len(ideation_docs)} ideation_results documents")
        
        # Parse and combine ideas
        all_ideas = []
        
        for doc in ideation_docs:
            try:
                logger.debug(f"Processing document with metadata: {doc.get('metadata', {})}")
                text = doc['text']
                # If the text looks like JSON but isn't properly formatted, try to clean it up
                if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
                    try:
                        data = json.loads(text)
                        if "ideas" in data and isinstance(data["ideas"], list):
                            all_ideas.extend(data["ideas"])
                        elif "id" in data and "title" in data:
                            # This appears to be a single idea document
                            all_ideas.append(data)
                            logger.debug("Added single idea document")
                    except json.JSONDecodeError:
                        # Try to extract JSON substring if possible
                        json_start = text.find("{")
                        json_end = text.rfind("}") + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = text[json_start:json_end]
                            try:
                                data = json.loads(json_str)
                                logger.debug(f"Successfully extracted JSON from text: {json_str[:100]}...")
                                if "ideas" in data and isinstance(data["ideas"], list):
                                    all_ideas.extend(data["ideas"])
                                elif "id" in data and "title" in data:
                                    all_ideas.append(data)
                                    logger.debug("Added single idea document from extracted JSON")
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse extracted JSON: {json_str[:100]}...")
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from document: {doc.get('text', '')[:100]}...")
                continue
            except Exception as e:
                logger.error(f"Error processing document: {str(e)}")
                continue
        
        if not all_ideas:
            logger.error(f"No valid ideas found after processing {len(ideation_docs)} documents")
            # Dump the first few docs for debugging
            for i, doc in enumerate(ideation_docs[:3]):
                logger.debug(f"Document {i}: {doc.get('text', '')[:100]}...")
            raise ValueError("No valid ideas found")
        
        # Get the selected idea
        selected_idea = None
        
        if selected_idea_id:
            # Find the specified idea
            for idea in all_ideas:
                if idea.get("id") == selected_idea_id:
                    selected_idea = idea
                    break
            
            if not selected_idea:
                logger.warning(f"Selected idea {selected_idea_id} not found, using best idea instead")
        
        if not selected_idea:
            # Use the highest-rated idea or first idea if no scores
            try:
                selected_idea = max(all_ideas, key=lambda x: float(x.get("score", 0)))
            except (ValueError, TypeError):
                logger.warning("Could not determine best idea based on score, using first idea")
                selected_idea = all_ideas[0]
        
        # Store the selected idea
        result = {
            "selected_idea": selected_idea,
            "all_ideas": all_ideas
        }
        
        self.memory.add_document(
            json.dumps(result),
            self.name,
            metadata={"type": "aggregated_ideation"}
        )
        
        return result
    
    def aggregate_character_data(self) -> Dict[str, Any]:
        """
        Aggregate data from the character development stage.
        
        Returns:
            Dictionary with aggregated character data
        """
        logger.info(f"Aggregating character data for project {self.project_id}")
        
        try:
            # Get character agent data
            character_docs = self.memory.query_memory("type:character", agent_name="character_agent")
            
            if not character_docs:
                logger.warning("No character data found with type:character query, trying alternative queries")
                # Try alternative queries
                character_docs = self.memory.get_agent_memory("character_agent")
                if not character_docs:
                    logger.warning("No documents found from character agent, providing fallback characters")
                    # Create fallback characters when no data exists
                    fallback_characters = {
                        "characters": [
                            {
                                "id": "fallback_protagonist",
                                "name": "Main Character",
                                "role": "protagonist",
                                "age": 30,
                                "physical_description": "Distinctive and memorable",
                                "personality": "Determined, adaptable",
                                "background": "Background that relates to the story",
                                "motivation": "To overcome the central conflict",
                                "goals": ["Achieve primary objective"],
                                "arc": "Personal growth through challenges",
                                "strengths": ["Resourcefulness"],
                                "flaws": ["Self-doubt"]
                            },
                            {
                                "id": "fallback_antagonist",
                                "name": "Opposing Force",
                                "role": "antagonist",
                                "age": 35,
                                "physical_description": "Imposing presence",
                                "personality": "Driven by clear motives",
                                "background": "History that explains their opposition",
                                "motivation": "Goals that conflict with protagonist",
                                "goals": ["Achieve their vision"],
                                "arc": "Path that challenges the protagonist",
                                "strengths": ["Determination"],
                                "flaws": ["Blind spot in reasoning"]
                            }
                        ],
                        "relationships": [
                            {
                                "character1_id": "fallback_protagonist",
                                "character2_id": "fallback_antagonist",
                                "relationship_type": "opposition",
                                "description": "Direct conflict of goals and values"
                            }
                        ]
                    }
                    
                    # Store the fallback data in memory
                    try:
                        self.memory.add_document(
                            json.dumps(fallback_characters),
                            self.name,
                            metadata={"type": "aggregated_characters", "is_fallback": True}
                        )
                        logger.info("Stored fallback character data in memory")
                    except Exception as e:
                        logger.error(f"Failed to store fallback character data: {e}")
                    
                    return fallback_characters
            
            # Parse and combine characters
            all_characters = []
            
            for doc in character_docs:
                try:
                    text = doc['text']
                    # Check if this is a single character or a characters collection
                    try:
                        data = json.loads(text)
                        
                        # If this is a collection with a characters array
                        if "characters" in data and isinstance(data["characters"], list):
                            for character in data["characters"]:
                                if character not in all_characters:
                                    all_characters.append(character)
                        # If this is a single character object
                        elif "id" in data and "name" in data:
                            if data not in all_characters:
                                all_characters.append(data)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse character JSON: {text[:100]}...")
                        continue
                except Exception as e:
                    logger.error(f"Error processing character document: {e}")
                    continue
            
            # Get character relationships
            relationship_docs = self.memory.query_memory("type:character_relationships", agent_name="character_agent")
            
            relationships = []
            if relationship_docs:
                for doc in relationship_docs:
                    try:
                        data = json.loads(doc['text'])
                        if "relationships" in data and isinstance(data["relationships"], list):
                            relationships.extend(data["relationships"])
                        elif "character1_id" in data and "character2_id" in data:
                            relationships.append(data)
                    except (json.JSONDecodeError, IndexError) as e:
                        logger.warning(f"Error parsing relationship data: {e}")
                        continue
            
            # If we parsed documents but ended up with no characters, provide fallback
            if not all_characters:
                logger.warning("No valid characters could be parsed from documents, using fallbacks")
                all_characters = [
                    {
                        "id": "hub_fallback_protagonist",
                        "name": "Main Character",
                        "role": "protagonist",
                        "background": "Character with a compelling backstory",
                        "motivation": "To overcome the central conflict of the story"
                    },
                    {
                        "id": "hub_fallback_antagonist",
                        "name": "Antagonist",
                        "role": "antagonist",
                        "background": "Character whose goals oppose the protagonist",
                        "motivation": "To achieve aims that conflict with the protagonist"
                    }
                ]
                
                # Create basic relationships if none exist
                if not relationships and len(all_characters) >= 2:
                    relationships = [
                        {
                            "character1_id": all_characters[0]["id"],
                            "character2_id": all_characters[1]["id"],
                            "relationship_type": "opposition",
                            "description": "Primary story conflict"
                        }
                    ]
            
            # Store the aggregated character data
            result = {
                "characters": all_characters,
                "relationships": relationships
            }
            
            try:
                self.memory.add_document(
                    json.dumps(result),
                    self.name,
                    metadata={"type": "aggregated_characters"}
                )
                logger.info(f"Stored aggregated character data with {len(all_characters)} characters and {len(relationships)} relationships")
            except Exception as e:
                logger.error(f"Failed to store aggregated character data: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in character data aggregation: {e}")
            # Final fallback in case of any unexpected errors
            fallback_result = {
                "characters": [
                    {
                        "id": "emergency_protagonist",
                        "name": "Protagonist",
                        "role": "protagonist",
                        "background": "Main character of the story",
                        "motivation": "To resolve the central conflict"
                    },
                    {
                        "id": "emergency_antagonist",
                        "name": "Antagonist",
                        "role": "antagonist",
                        "background": "Character opposing the protagonist",
                        "motivation": "To achieve opposing goals"
                    }
                ],
                "relationships": [
                    {
                        "character1_id": "emergency_protagonist",
                        "character2_id": "emergency_antagonist",
                        "relationship_type": "conflict",
                        "description": "Central story conflict"
                    }
                ]
            }
            return fallback_result
    
    def aggregate_world_data(self) -> Dict[str, Any]:
        """
        Aggregate data from the world building stage.
        
        Returns:
            Dictionary with aggregated world data
        """
        logger.info(f"Aggregating world data for project {self.project_id}")
        
        # Get world building agent data
        world_docs = self.memory.query_memory("type:world", agent_name="world_building_agent")
        
        if not world_docs:
            raise ValueError("No world data found")
        
        # Get the main world data
        try:
            world_data = json.loads(world_docs[0]['text'])
        except (json.JSONDecodeError, IndexError):
            raise ValueError("Invalid world data")
        
        # Get additional location data
        location_docs = self.memory.query_memory("type:location", agent_name="world_building_agent")
        
        locations = []
        for doc in location_docs:
            try:
                location = json.loads(doc['text'])
                locations.append(location)
            except json.JSONDecodeError:
                continue
        
        # Get cultural elements
        culture_docs = self.memory.query_memory("type:cultural_element", agent_name="world_building_agent")
        
        cultural_elements = []
        for doc in culture_docs:
            try:
                element = json.loads(doc['text'])
                cultural_elements.append(element)
            except json.JSONDecodeError:
                continue
        
        # Merge data
        if "locations" in world_data:
            # Add any locations not already in world_data
            existing_names = {loc.get("name") for loc in world_data["locations"]}
            new_locations = [loc for loc in locations if loc.get("name") not in existing_names]
            world_data["locations"].extend(new_locations)
        else:
            world_data["locations"] = locations
        
        if "cultural_elements" in world_data:
            # Add any elements not already in world_data
            existing_names = {elem.get("name") for elem in world_data["cultural_elements"]}
            new_elements = [elem for elem in cultural_elements if elem.get("name") not in existing_names]
            world_data["cultural_elements"].extend(new_elements)
        else:
            world_data["cultural_elements"] = cultural_elements
        
        # Store the aggregated world data
        self.memory.add_document(
            json.dumps(world_data),
            self.name,
            metadata={"type": "aggregated_world"}
        )
        
        return world_data
    
    def aggregate_research_data(self) -> Dict[str, Any]:
        """
        Aggregate data from the research stage.
        
        Returns:
            Dictionary with aggregated research data
        """
        logger.info(f"Aggregating research data for project {self.project_id}")
        
        try:
            # Get research agent data
            topic_docs = self.memory.query_memory("type:topic", agent_name="research_agent")
            
            # If no topics found, try to look for any research data
            if not topic_docs:
                logger.warning(f"No topic data found for project {self.project_id}, checking for other research data")
                research_docs = self.memory.query_memory("type:research_results", agent_name="research_agent")
                
                if research_docs:
                    logger.info(f"Found research results data for project {self.project_id}")
                    try:
                        research_data = json.loads(research_docs[0]['text'])
                        if "topics" in research_data and isinstance(research_data["topics"], list):
                            # Extract topics from research results
                            for topic in research_data["topics"]:
                                self.memory.add_document(
                                    json.dumps(topic),
                                    "research_agent",
                                    metadata={"type": "topic", "topic_id": topic.get("id", "unknown")}
                                )
                            topic_docs = self.memory.query_memory("type:topic", agent_name="research_agent")
                    except (json.JSONDecodeError, IndexError):
                        logger.warning("Failed to extract topics from research results")
            
            # If still no topics, create fallback topics
            if not topic_docs:
                logger.warning(f"No research data found for project {self.project_id}, creating fallback topics")
                # Create fallback topics
                fallback_topics = [
                    {
                        "id": "fallback_topic_1",
                        "name": "Setting Research",
                        "description": "Understanding the physical and cultural environment of the story",
                        "importance": "Essential for creating an immersive world"
                    },
                    {
                        "id": "fallback_topic_2",
                        "name": "Character Background Research",
                        "description": "Researching professions, skills, and psychological traits",
                        "importance": "Critical for authentic character portrayal"
                    }
                ]
                
                # Add fallback topics to memory
                for topic in fallback_topics:
                    self.memory.add_document(
                        json.dumps(topic),
                        "research_agent",
                        metadata={"type": "topic", "topic_id": topic["id"]}
                    )
                
                topic_docs = self.memory.query_memory("type:topic", agent_name="research_agent")
            
            # Parse and combine topics
            all_topics = []
            
            for doc in topic_docs:
                try:
                    data = json.loads(doc['text'])
                    all_topics.append(data)
                except json.JSONDecodeError:
                    continue
            
            # Get detailed research
            detailed_docs = self.memory.query_memory("type:detailed_research", agent_name="research_agent")
            
            detailed_research = []
            for doc in detailed_docs:
                try:
                    data = json.loads(doc['text'])
                    detailed_research.append(data)
                except json.JSONDecodeError:
                    continue
            
            # Get research synthesis if available
            synthesis_docs = self.memory.query_memory("type:research_synthesis", agent_name="research_agent")
            
            synthesis = None
            if synthesis_docs:
                try:
                    synthesis = json.loads(synthesis_docs[0]['text'])
                except (json.JSONDecodeError, IndexError):
                    logger.warning("Failed to parse research synthesis data")
            
            # If no synthesis, create a simple fallback synthesis
            if not synthesis:
                logger.warning("No research synthesis found, creating fallback synthesis")
                synthesis = {
                    "overview": "Research provides context and authenticity for the story.",
                    "key_findings": [
                        {
                            "topic": "Story Environment",
                            "critical_points": ["Consider how setting influences character actions"]
                        }
                    ],
                    "connections": [],
                    "writing_recommendations": ["Integrate research naturally into the narrative"],
                    "research_gaps": ["Consider additional research as needed during writing"]
                }
                
                # Add fallback synthesis to memory
                self.memory.add_document(
                    json.dumps(synthesis),
                    "research_agent",
                    metadata={"type": "research_synthesis"}
                )
            
            # Store the aggregated research data
            result = {
                "topics": all_topics,
                "detailed_research": detailed_research,
                "synthesis": synthesis
            }
            
            self.memory.add_document(
                json.dumps(result),
                self.name,
                metadata={"type": "aggregated_research"}
            )
            
            return result
        except Exception as e:
            logger.error(f"Error aggregating research data: {e}")
            # Return minimal fallback data to allow workflow to continue
            fallback_result = {
                "topics": [
                    {
                        "id": "fallback_topic",
                        "name": "General Story Research",
                        "description": "Basic background information for the story",
                        "importance": "Provides authenticity to the narrative"
                    }
                ],
                "detailed_research": [],
                "synthesis": {
                    "overview": "Basic research will help provide authenticity to the narrative.",
                    "key_findings": [{"topic": "General Research", "critical_points": ["Consider story authenticity"]}],
                    "connections": [],
                    "writing_recommendations": ["Focus on character development"],
                    "research_gaps": ["May need additional specific research"]
                }
            }
            
            # Store the fallback data
            self.memory.add_document(
                json.dumps(fallback_result),
                self.name,
                metadata={"type": "aggregated_research"}
            )
            
            return fallback_result
    
    def integrate_all_data(self) -> Dict[str, Any]:
        """
        Integrate all data from previous stages for outlining and writing.
        
        Returns:
            Dictionary with integrated data
        """
        logger.info(f"Integrating all data for project {self.project_id}")
        
        # Initialize variables
        ideation_data = None
        character_data = None
        world_data = None
        research_data = None
        
        # Ensure we have all required data
        try:
            ideation_data = self.get_aggregated_data("ideation")
            character_data = self.get_aggregated_data("characters")
            world_data = self.get_aggregated_data("world")
            research_data = self.get_aggregated_data("research")
        except ValueError as e:
            logger.warning(f"Missing some data: {e}")
            
            # Try to aggregate any missing data
            if not ideation_data:
                try:
                    ideation_data = self.aggregate_ideation_data()
                except ValueError:
                    ideation_data = {}
            
            if not character_data:
                try:
                    character_data = self.aggregate_character_data()
                except ValueError:
                    character_data = {"characters": [], "relationships": []}
            
            if not world_data:
                try:
                    world_data = self.aggregate_world_data()
                except ValueError:
                    world_data = {}
            
            if not research_data:
                try:
                    research_data = self.aggregate_research_data()
                except ValueError:
                    research_data = {"topics": [], "detailed_research": [], "synthesis": None}
        
        # Create the integrated data
        selected_idea = ideation_data.get("selected_idea", {}) if ideation_data else {}
        
        integrated_data = {
            "book_idea": selected_idea,
            "characters": character_data.get("characters", []) if character_data else [],
            "character_relationships": character_data.get("relationships", []) if character_data else [],
            "world": world_data if world_data else {},
            "research": {
                "topics": research_data.get("topics", []) if research_data else [],
                "key_findings": research_data.get("synthesis", {}).get("key_findings", []) 
                               if research_data and research_data.get("synthesis") else []
            }
        }
        
        # Store the integrated data
        self.memory.add_document(
            json.dumps(integrated_data),
            self.name,
            metadata={"type": "integrated_data"}
        )
        
        return integrated_data
    
    def get_aggregated_data(self, data_type: str) -> Dict[str, Any]:
        """
        Get previously aggregated data.
        
        Args:
            data_type: Type of data to retrieve ('ideation', 'characters', 'world', 'research')
            
        Returns:
            Dictionary with the aggregated data
        """
        # Map data type to query
        query_map = {
            "ideation": "type:aggregated_ideation",
            "characters": "type:aggregated_characters",
            "world": "type:aggregated_world",
            "research": "type:aggregated_research",
            "integrated": "type:integrated_data"
        }
        
        if data_type not in query_map:
            raise ValueError(f"Invalid data type: {data_type}")
        
        # Query for data
        docs = self.memory.query_memory(query_map[data_type], agent_name=self.name)
        
        if not docs:
            raise ValueError(f"No {data_type} data found")
        
        try:
            return json.loads(docs[0]['text'])
        except (json.JSONDecodeError, IndexError):
            raise ValueError(f"Invalid {data_type} data")
    
    def get_integrated_data(self) -> Dict[str, Any]:
        """
        Get the integrated data for outlining and writing.
        
        Returns:
            Dictionary with integrated data
        """
        try:
            return self.get_aggregated_data("integrated")
        except ValueError:
            # If integrated data doesn't exist, create it
            return self.integrate_all_data()
    
    def update_project_status(self, status: Dict[str, Any]) -> None:
        """
        Update the project status.
        
        Args:
            status: Dictionary with project status information
        """
        # Add timestamp to status if not present
        if "last_updated" not in status:
            import datetime
            status["last_updated"] = datetime.datetime.now().isoformat()
            
        # Log status update
        logger.info(f"Updating project status for {self.project_id}: {status.get('status')} - {status.get('current_stage')} - {status.get('progress')}%")
        
        # Store the status
        self.memory.add_document(
            json.dumps(status),
            self.name,
            metadata={"type": "project_status", "timestamp": status.get("last_updated")}
        )
    
    def get_project_status(self) -> Dict[str, Any]:
        """
        Get the current status of the project.
        
        Returns:
            Dictionary with project status information
        """
        # Attempt to retrieve existing status
        status_docs = self.memory.query_memory("type:project_status")
        
        if status_docs:
            try:
                latest_status = json.loads(status_docs[0]['text'])
                return latest_status
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                logger.warning(f"Error parsing existing project status: {e}")
        
        # If no status or error parsing, return default status
        return {
            "status": "not_started",
            "current_stage": "not_started",
            "progress": 0,
            "completed_stages": []
        }
    
    def get_timeline(self) -> List[Dict[str, Any]]:
        """
        Get the timeline of events for the project.
        
        Returns:
            List of dictionaries with timeline events
        """
        timeline = []
        
        # Query documents with timestamps
        docs = self.memory.query_memory("type:*")
        
        for doc in docs:
            try:
                # Extract metadata if it exists
                metadata = doc.get('metadata', {})
                timestamp = metadata.get('timestamp')
                doc_type = metadata.get('type', 'unknown')
                agent = metadata.get('agent', 'system')
                
                if timestamp:
                    event = {
                        "timestamp": timestamp,
                        "event_type": doc_type,
                        "agent": agent,
                        "description": f"{agent} completed {doc_type}"
                    }
                    timeline.append(event)
            except Exception as e:
                logger.warning(f"Error parsing document for timeline: {e}")
        
        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x.get('timestamp', ''))
        
        return timeline
        
    def get_top_ideas(self, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get the top ideas for the project.
        
        Args:
            limit: Maximum number of ideas to return
            
        Returns:
            List of dictionaries with top ideas
        """
        # Try to get aggregated ideation data
        try:
            ideation_data = self.get_aggregated_data("ideation")
            if ideation_data and "all_ideas" in ideation_data:
                # Sort ideas by score if present
                try:
                    sorted_ideas = sorted(
                        ideation_data["all_ideas"], 
                        key=lambda x: float(x.get("score", 0)), 
                        reverse=True
                    )
                    return sorted_ideas[:limit]
                except (ValueError, TypeError):
                    # If sorting fails, just return the first few
                    return ideation_data["all_ideas"][:limit]
        except ValueError:
            pass
        
        # If no aggregated data, try to get individual idea documents
        idea_docs = self.memory.query_memory("type:idea", agent_name="ideation_agent")
        
        ideas = []
        for doc in idea_docs:
            try:
                idea = json.loads(doc['text'])
                ideas.append(idea)
            except json.JSONDecodeError:
                continue
        
        # Return up to limit ideas
        return ideas[:limit]
