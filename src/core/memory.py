"""Long-term memory system using vector embeddings."""

import chromadb
from openai import OpenAI
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class FinancialSituationMemory:
    """
    Long-term memory for storing and retrieving financial situations and lessons.
    Uses ChromaDB for vector storage and OpenAI embeddings.
    """

    def __init__(self, name: str, config):
        """Initialize memory system."""
        self.name = name
        self.config = config
        self.embedding_model = config.EMBEDDING_MODEL

        # Initialize OpenAI client
        try:
            self.client = OpenAI(base_url=config.LLM_BACKEND_URL, api_key=config.OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

        # Initialize ChromaDB
        try:
            persistence_dir = Path(config.MEMORY_PERSISTENCE_DIR) / name
            persistence_dir.mkdir(parents=True, exist_ok=True)

            self.chroma_client = chromadb.PersistentClient(path=str(persistence_dir))
            self.situation_collection = self.chroma_client.get_or_create_collection(
                name=name,
                metadata={"description": f"Financial situations for {name}"}
            )
            logger.info(f"Initialized memory '{name}' with {self.situation_collection.count()} memories")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        try:
            response = self.client.embeddings.create(model=self.embedding_model, input=text)
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]) -> None:
        """Add new situations and their lessons to memory."""
        if not situations_and_advice:
            return

        try:
            offset = self.situation_collection.count()
            ids = [str(offset + i) for i, _ in enumerate(situations_and_advice)]

            situations = [s for s, r in situations_and_advice]
            recommendations = [r for s, r in situations_and_advice]

            embeddings = [self.get_embedding(s) for s in situations]

            self.situation_collection.add(
                documents=situations,
                metadatas=[{"recommendation": rec} for rec in recommendations],
                embeddings=embeddings,
                ids=ids,
            )

            logger.info(f"Added {len(situations_and_advice)} situations to memory '{self.name}'")
            self._prune_if_needed()

        except Exception as e:
            logger.error(f"Failed to add situations: {e}")

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Retrieve similar past situations and their lessons."""
        if self.situation_collection.count() == 0:
            return []

        try:
            query_embedding = self.get_embedding(current_situation)

            results = self.situation_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_matches, self.situation_collection.count()),
                include=["metadatas", "distances"],
            )

            memories = []
            threshold = self.config.SIMILARITY_THRESHOLD

            for meta, distance in zip(results['metadatas'][0], results['distances'][0]):
                similarity = 1 - distance
                if similarity >= threshold:
                    memories.append({
                        'recommendation': meta['recommendation'],
                        'similarity': similarity
                    })

            return memories

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    def _prune_if_needed(self) -> None:
        """Prune old memories if exceeding maximum."""
        count = self.situation_collection.count()
        max_memories = self.config.MAX_MEMORIES

        if count > max_memories:
            to_delete = count - max_memories
            ids_to_delete = [str(i) for i in range(to_delete)]
            try:
                self.situation_collection.delete(ids=ids_to_delete)
                logger.info(f"Pruned {to_delete} old memories from '{self.name}'")
            except Exception as e:
                logger.warning(f"Failed to prune memories: {e}")

    def clear(self) -> None:
        """Clear all memories."""
        try:
            self.chroma_client.delete_collection(name=self.name)
            self.situation_collection = self.chroma_client.create_collection(name=self.name)
            logger.info(f"Cleared all memories from '{self.name}'")
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
