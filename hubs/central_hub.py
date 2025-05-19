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
            raise ValueError("No ideation data found")
        
        # Parse and combine ideas
        all_ideas = []
        
        for doc in ideation_docs:
            try:
                data = json.loads(doc['text'])
                if "ideas" in data and isinstance(data["ideas"], list):
                    all_ideas.extend(data["ideas"])
            except json.JSONDecodeError:
                continue
        
        if not all_ideas:
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
            # Use the highest-rated idea
            selected_idea = max(all_ideas, key=lambda x: float(x.get("score", 0)))
        
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
        
        # Get character agent data
        character_docs = self.memory.query_memory("type:character", agent_name="character_agent")
        
        if not character_docs:
            raise ValueError("No character data found")
        
        # Parse and combine characters
        all_characters = []
        
        for doc in character_docs:
            try:
                data = json.loads(doc['text'])
                all_characters.append(data)
            except json.JSONDecodeError:
                continue
        
        # Get character relationships
        relationship_docs = self.memory.query_memory("type:character_relationships", agent_name="character_agent")
        
        relationships = []
        if relationship_docs:
            try:
                data = json.loads(relationship_docs[0]['text'])
                if "relationships" in data and isinstance(data["relationships"], list):
                    relationships = data["relationships"]
            except (json.JSONDecodeError, IndexError):
                pass
        
        # Store the aggregated character data
        result = {
            "characters": all_characters,
            "relationships": relationships
        }
        
        self.memory.add_document(
            json.dumps(result),
            self.name,
            metadata={"type": "aggregated_characters"}
        )
        
        return result
    
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
        
        # Get research agent data
        topic_docs = self.memory.query_memory("type:topic", agent_name="research_agent")
        
        if not topic_docs:
            raise ValueError("No research data found")
        
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
                pass
        
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
    
    def integrate_all_data(self) -> Dict[str, Any]:
        """
        Integrate all data from previous stages for outlining and writing.
        
        Returns:
            Dictionary with integrated data
        """
        logger.info(f"Integrating all data for project {self.project_id}")
        
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
        # Store the status
        self.memory.add_document(
            json.dumps(status),
            self.name,
            metadata={"type": "project_status"}
        )
    
    def get_project_status(self) -> Dict[str, Any]:
        """
        Get the current project status.
        
        Returns:
            Dictionary with project status
        """
        # Query for status
        docs = self.memory.query_memory("type:project_status", agent_name=self.name)
        
        if not docs:
            return {"status": "not_started", "progress": 0, "current_stage": None}
        
        try:
            return json.loads(docs[0]['text'])
        except (json.JSONDecodeError, IndexError):
            return {"status": "error", "progress": 0, "current_stage": None}
