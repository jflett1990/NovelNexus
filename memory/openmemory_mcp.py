"""
OpenMemory MCP Server integration for NovelNexus.
Provides persistent, structured memory for novel generation with plot consistency.
"""

import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid
import os

logger = logging.getLogger(__name__)

class OpenMemoryMCP:
    """
    OpenMemory MCP Server client for persistent novel memory management.
    Handles plot continuity, character consistency, and cross-chapter references.
    """
    
    def __init__(
        self,
        project_id: str,
        server_url: str = "http://localhost:3434",
        timeout: int = 30
    ):
        """
        Initialize OpenMemory MCP client.
        
        Args:
            project_id: Unique identifier for the novel project
            server_url: OpenMemory MCP server URL
            timeout: Request timeout in seconds
        """
        self.project_id = project_id
        self.server_url = server_url
        self.timeout = timeout
        self.session = None
        self._use_fallback = False
        self.fallback_dir = None
        
        # Novel-specific memory categories
        self.memory_categories = {
            "plot_points": {
                "schema": {
                    "chapter": "int",
                    "location": "str",
                    "conflict": "str",
                    "resolution": "str",
                    "characters_involved": "list[str]"
                }
            },
            "character_profiles": {
                "schema": {
                    "name": "str",
                    "traits": "list[str]",
                    "arc_stage": "str",
                    "relationships": "dict",
                    "last_appearance": "int"
                }
            },
            "world_elements": {
                "schema": {
                    "name": "str",
                    "type": "str",  # location, rule, technology, etc.
                    "description": "str",
                    "first_introduced": "int",
                    "consistency_rules": "list[str]"
                }
            },
            "narrative_threads": {
                "schema": {
                    "thread_id": "str",
                    "description": "str",
                    "status": "str",  # active, resolved, abandoned
                    "chapters": "list[int]",
                    "resolution_chapter": "int"
                }
            },
            "style_templates": {
                "schema": {
                    "style_name": "str",
                    "tone": "str",
                    "pacing": "str",
                    "dialogue_ratio": "float",
                    "example_text": "str"
                }
            }
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        await self._initialize_project_memory()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _initialize_project_memory(self):
        """Initialize memory categories for the novel project."""
        try:
            # Check if server is running
            await self._health_check()
            
            # Initialize memory categories
            for category, config in self.memory_categories.items():
                await self._create_memory_category(category, config["schema"])
                
            logger.info(f"Initialized OpenMemory for project {self.project_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenMemory: {e}")
            raise
    
    async def _health_check(self):
        """Check if OpenMemory server is running."""
        try:
            async with self.session.get(f"{self.server_url}/health") as response:
                if response.status != 200:
                    raise ConnectionError(f"OpenMemory server not healthy: {response.status}")
        except aiohttp.ClientError as e:
            # If MCP server is not available, switch to fallback mode
            logger.warning(f"MCP server not available, switching to fallback memory: {e}")
            self._use_fallback = True
            await self._initialize_fallback_memory()
        except Exception as e:
            logger.warning(f"MCP server check failed, switching to fallback memory: {e}")
            self._use_fallback = True
            await self._initialize_fallback_memory()

    async def _initialize_fallback_memory(self):
        """Initialize fallback file-based memory system."""
        self.fallback_dir = f"memory_data/{self.project_id}"
        os.makedirs(self.fallback_dir, exist_ok=True)

        # Initialize category files
        for category in self.memory_categories.keys():
            category_file = os.path.join(self.fallback_dir, f"{category}.json")
            if not os.path.exists(category_file):
                with open(category_file, 'w') as f:
                    json.dump([], f)

        logger.info(f"Initialized fallback memory system at {self.fallback_dir}")
    
    async def _create_memory_category(self, category: str, schema: Dict[str, str]):
        """Create a memory category with schema validation."""
        payload = {
            "category": f"{self.project_id}_{category}",
            "schema": schema,
            "metadata": {
                "project_id": self.project_id,
                "created_at": datetime.now().isoformat()
            }
        }
        
        try:
            async with self.session.post(
                f"{self.server_url}/api/categories",
                json=payload
            ) as response:
                if response.status not in [200, 201, 409]:  # 409 = already exists
                    error_text = await response.text()
                    logger.warning(f"Failed to create category {category}: {error_text}")
        except Exception as e:
            logger.error(f"Error creating memory category {category}: {e}")
    
    async def add_plot_point(
        self,
        chapter: int,
        location: str,
        conflict: str,
        resolution: str = "",
        characters_involved: List[str] = None
    ) -> str:
        """Add a plot point to memory."""
        memory_data = {
            "chapter": chapter,
            "location": location,
            "conflict": conflict,
            "resolution": resolution,
            "characters_involved": characters_involved or []
        }
        
        return await self._add_memory(
            "plot_points",
            f"Chapter {chapter}: {conflict} at {location}",
            memory_data
        )
    
    async def add_character_profile(
        self,
        name: str,
        traits: List[str],
        arc_stage: str = "introduction",
        relationships: Dict[str, str] = None,
        last_appearance: int = 1
    ) -> str:
        """Add or update a character profile."""
        memory_data = {
            "name": name,
            "traits": traits,
            "arc_stage": arc_stage,
            "relationships": relationships or {},
            "last_appearance": last_appearance
        }
        
        return await self._add_memory(
            "character_profiles",
            f"Character profile: {name}",
            memory_data
        )
    
    async def add_world_element(
        self,
        name: str,
        element_type: str,
        description: str,
        first_introduced: int,
        consistency_rules: List[str] = None
    ) -> str:
        """Add a world element to memory."""
        memory_data = {
            "name": name,
            "type": element_type,
            "description": description,
            "first_introduced": first_introduced,
            "consistency_rules": consistency_rules or []
        }
        
        return await self._add_memory(
            "world_elements",
            f"{element_type}: {name}",
            memory_data
        )
    
    async def track_narrative_thread(
        self,
        thread_id: str,
        description: str,
        status: str = "active",
        chapters: List[int] = None,
        resolution_chapter: int = None
    ) -> str:
        """Track a narrative thread across chapters."""
        memory_data = {
            "thread_id": thread_id,
            "description": description,
            "status": status,
            "chapters": chapters or [],
            "resolution_chapter": resolution_chapter
        }
        
        return await self._add_memory(
            "narrative_threads",
            f"Thread: {description}",
            memory_data
        )
    
    async def save_style_template(
        self,
        style_name: str,
        tone: str,
        pacing: str,
        dialogue_ratio: float,
        example_text: str
    ) -> str:
        """Save a successful writing style as a template."""
        memory_data = {
            "style_name": style_name,
            "tone": tone,
            "pacing": pacing,
            "dialogue_ratio": dialogue_ratio,
            "example_text": example_text
        }
        
        return await self._add_memory(
            "style_templates",
            f"Style template: {style_name}",
            memory_data
        )
    
    async def _add_memory(self, category: str, content: str, structured_data: Dict[str, Any]) -> str:
        """Add structured memory to a specific category."""
        memory_id = str(uuid.uuid4())

        if self._use_fallback:
            return await self._add_memory_fallback(category, content, structured_data, memory_id)

        payload = {
            "content": content,
            "metadata": {
                "category": f"{self.project_id}_{category}",
                "project_id": self.project_id,
                "structured_data": structured_data,
                "timestamp": datetime.now().isoformat()
            }
        }

        try:
            async with self.session.post(
                f"{self.server_url}/api/memories",
                json=payload
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    memory_id = result.get("id", memory_id)
                    logger.debug(f"Added {category} memory: {memory_id}")
                    return memory_id
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to add {category} memory: {error_text}")
                    return ""
        except Exception as e:
            logger.error(f"Error adding {category} memory: {e}")
            # Fallback to file-based storage
            return await self._add_memory_fallback(category, content, structured_data, memory_id)

    async def _add_memory_fallback(self, category: str, content: str, structured_data: Dict[str, Any], memory_id: str) -> str:
        """Add memory using fallback file-based storage."""
        try:
            category_file = os.path.join(self.fallback_dir, f"{category}.json")

            # Read existing memories
            with open(category_file, 'r') as f:
                memories = json.load(f)

            # Add new memory
            memory_entry = {
                "id": memory_id,
                "content": content,
                "structured_data": structured_data,
                "timestamp": datetime.now().isoformat(),
                "category": category,
                "project_id": self.project_id
            }

            memories.append(memory_entry)

            # Write back to file
            with open(category_file, 'w') as f:
                json.dump(memories, f, indent=2)

            logger.debug(f"Added {category} memory to fallback storage: {memory_id}")
            return memory_id

        except Exception as e:
            logger.error(f"Error adding {category} memory to fallback: {e}")
            return ""
    
    async def search_memories(
        self,
        query: str,
        category: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search memories with optional category filter."""
        if self._use_fallback:
            return await self._search_memories_fallback(query, category, limit)

        params = {
            "query": query,
            "limit": limit
        }

        if category:
            params["category"] = f"{self.project_id}_{category}"

        try:
            async with self.session.get(
                f"{self.server_url}/api/memories/search",
                params=params
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    return results.get("memories", [])
                else:
                    logger.error(f"Search failed: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            # Fallback to file-based search
            return await self._search_memories_fallback(query, category, limit)

    async def _search_memories_fallback(self, query: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories using fallback file-based storage."""
        try:
            results = []
            categories_to_search = [category] if category else list(self.memory_categories.keys())

            for cat in categories_to_search:
                category_file = os.path.join(self.fallback_dir, f"{cat}.json")
                if not os.path.exists(category_file):
                    continue

                with open(category_file, 'r') as f:
                    memories = json.load(f)

                # Simple text search (in a real implementation, you'd use better search)
                for memory in memories:
                    if (query.lower() in memory.get("content", "").lower() or
                        query.lower() in str(memory.get("structured_data", {})).lower()):
                        results.append({
                            "id": memory["id"],
                            "content": memory["content"],
                            "metadata": {
                                "structured_data": memory["structured_data"],
                                "timestamp": memory["timestamp"],
                                "category": memory["category"]
                            }
                        })

            # Sort by timestamp and limit
            results.sort(key=lambda x: x["metadata"]["timestamp"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error searching fallback memories: {e}")
            return []
    
    async def get_character_consistency(self, character_name: str) -> Dict[str, Any]:
        """Get character consistency information."""
        memories = await self.search_memories(
            f"character {character_name}",
            category="character_profiles"
        )
        
        if memories:
            return memories[0].get("metadata", {}).get("structured_data", {})
        return {}
    
    async def get_plot_continuity(self, chapter_range: tuple = None) -> List[Dict[str, Any]]:
        """Get plot continuity information for chapter range."""
        query = "plot point"
        if chapter_range:
            query += f" chapter {chapter_range[0]} to {chapter_range[1]}"
        
        memories = await self.search_memories(query, category="plot_points")
        return [m.get("metadata", {}).get("structured_data", {}) for m in memories]
    
    async def check_world_consistency(self, element_name: str) -> Dict[str, Any]:
        """Check world element consistency rules."""
        memories = await self.search_memories(
            f"world element {element_name}",
            category="world_elements"
        )
        
        if memories:
            return memories[0].get("metadata", {}).get("structured_data", {})
        return {}
