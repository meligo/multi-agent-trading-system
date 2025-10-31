"""
Trading Memory System with ChromaDB Vector Store

Provides long-term memory for trading agents to learn from past decisions.
Stores situations, decisions, outcomes, and reflections using vector similarity search.
"""

import chromadb
from openai import OpenAI
from typing import List, Dict, Optional
from forex_config import ForexConfig
import os


class TradingMemory:
    """
    Long-term memory for trading agents using ChromaDB vector store.

    Stores:
    - Market situations (technical setup, sentiment, news)
    - Agent decisions and reasoning
    - Actual outcomes (profit/loss)
    - Reflection lessons learned

    Retrieves similar past situations before new decisions to improve performance.
    """

    def __init__(self, name: str, persist_directory: str = "./chroma_db"):
        """
        Initialize trading memory.

        Args:
            name: Name for this memory collection (e.g., "bull_agent", "risk_manager")
            persist_directory: Directory to persist ChromaDB data
        """
        self.name = name
        self.embedding_model = "text-embedding-3-small"
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Create persistent ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)

        # Get or create collection
        try:
            self.collection = self.chroma_client.get_collection(name=name)
            print(f"✅ Loaded existing memory: {name} ({self.collection.count()} memories)")
        except:
            self.collection = self.chroma_client.create_collection(name=name)
            print(f"✅ Created new memory: {name}")

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text using OpenAI."""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"⚠️  Embedding generation failed: {e}")
            return None

    def add_memory(
        self,
        situation: str,
        decision: str,
        outcome: float,
        reflection: str,
        metadata: Optional[Dict] = None
    ):
        """
        Add a single memory to the store.

        Args:
            situation: Description of market situation and analysis
            decision: What decision was made (BUY/SELL/HOLD) and reasoning
            outcome: Actual profit/loss result
            reflection: Lesson learned from this outcome
            metadata: Additional context (pair, timeframe, confidence, etc.)
        """
        # Create comprehensive document combining all information
        full_situation = f"""
Market Situation:
{situation}

Decision Made:
{decision}

Outcome: {outcome:+.2f}%

Lesson Learned:
{reflection}
"""

        embedding = self.get_embedding(situation)  # Embed just the situation for retrieval
        if embedding is None:
            return

        # Build metadata
        meta = metadata or {}
        meta.update({
            "decision": decision,
            "outcome": outcome,
            "reflection": reflection
        })

        # Add to collection
        offset = self.collection.count()
        self.collection.add(
            documents=[full_situation],
            embeddings=[embedding],
            metadatas=[meta],
            ids=[f"{self.name}_{offset}"]
        )

    def add_memories(self, situations_and_lessons: List[tuple]):
        """
        Bulk add memories (for backward compatibility with notebook format).

        Args:
            situations_and_lessons: List of (situation, reflection) tuples
        """
        if not situations_and_lessons:
            return

        offset = self.collection.count()

        situations = [s for s, r in situations_and_lessons]
        reflections = [r for s, r in situations_and_lessons]
        embeddings = [self.get_embedding(s) for s in situations]

        # Filter out failed embeddings
        valid_data = [
            (s, r, e, f"{self.name}_{offset + i}")
            for i, (s, r, e) in enumerate(zip(situations, reflections, embeddings))
            if e is not None
        ]

        if not valid_data:
            return

        situations, reflections, embeddings, ids = zip(*valid_data)

        self.collection.add(
            documents=list(situations),
            metadatas=[{"reflection": r} for r in reflections],
            embeddings=list(embeddings),
            ids=list(ids)
        )

    def get_similar_situations(
        self,
        current_situation: str,
        n_matches: int = 3
    ) -> List[Dict]:
        """
        Retrieve similar past situations to learn from.

        Args:
            current_situation: Description of current market situation
            n_matches: Number of similar situations to retrieve

        Returns:
            List of dictionaries with 'situation', 'reflection', 'outcome', etc.
        """
        if self.collection.count() == 0:
            return []

        query_embedding = self.get_embedding(current_situation)
        if query_embedding is None:
            return []

        n_results = min(n_matches, self.collection.count())

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        memories = []
        for i in range(len(results['documents'][0])):
            memory = {
                'situation': results['documents'][0][i],
                'distance': results['distances'][0][i],
                **results['metadatas'][0][i]
            }
            memories.append(memory)

        return memories

    def get_memories(self, current_situation: str, n_matches: int = 3) -> List[Dict]:
        """
        Alias for get_similar_situations (backward compatibility with notebook).
        """
        results = self.get_similar_situations(current_situation, n_matches)
        # Return in format expected by notebook code
        return [{'recommendation': mem.get('reflection', '')} for mem in results]

    def get_performance_stats(self) -> Dict:
        """Get statistics on stored memories and outcomes."""
        if self.collection.count() == 0:
            return {"total": 0}

        # Get all memories
        all_data = self.collection.get(include=["metadatas"])

        outcomes = [
            float(meta.get('outcome', 0))
            for meta in all_data['metadatas']
            if 'outcome' in meta
        ]

        if not outcomes:
            return {
                "total": self.collection.count(),
                "avg_outcome": 0,
                "win_rate": 0
            }

        wins = sum(1 for o in outcomes if o > 0)

        return {
            "total": self.collection.count(),
            "avg_outcome": sum(outcomes) / len(outcomes),
            "win_rate": wins / len(outcomes) if outcomes else 0,
            "best_trade": max(outcomes),
            "worst_trade": min(outcomes)
        }

    def clear(self):
        """Clear all memories (use with caution!)."""
        self.chroma_client.delete_collection(name=self.name)
        self.collection = self.chroma_client.create_collection(name=self.name)
        print(f"🗑️  Cleared all memories for {self.name}")


class MemoryManager:
    """Manages memories for all trading agents."""

    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory

        # Create memory for each agent type
        self.bull_memory = TradingMemory("bull_agent", persist_directory)
        self.bear_memory = TradingMemory("bear_agent", persist_directory)
        self.momentum_memory = TradingMemory("momentum_agent", persist_directory)
        self.price_action_memory = TradingMemory("price_action_agent", persist_directory)
        self.decision_maker_memory = TradingMemory("decision_maker", persist_directory)
        self.risk_manager_memory = TradingMemory("risk_manager", persist_directory)
        self.trader_memory = TradingMemory("trader", persist_directory)

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get performance statistics for all agents."""
        return {
            "bull_agent": self.bull_memory.get_performance_stats(),
            "bear_agent": self.bear_memory.get_performance_stats(),
            "momentum_agent": self.momentum_memory.get_performance_stats(),
            "price_action_agent": self.price_action_memory.get_performance_stats(),
            "decision_maker": self.decision_maker_memory.get_performance_stats(),
            "risk_manager": self.risk_manager_memory.get_performance_stats(),
            "trader": self.trader_memory.get_performance_stats()
        }


# Test function
def test_trading_memory():
    """Test the trading memory system."""
    print("Testing Trading Memory System...")
    print("=" * 70)

    # Create a test memory
    memory = TradingMemory("test_agent", "./chroma_db_test")

    # Add some test memories
    print("\n📝 Adding test memories...")
    memory.add_memory(
        situation="EUR/USD showing bullish MACD crossover, RSI at 65, strong uptrend on 5m timeframe",
        decision="BUY signal with 80% confidence, entry at 1.0850",
        outcome=2.5,
        reflection="Bullish MACD crossovers on 5m with RSI 60-70 tend to be reliable in strong trends",
        metadata={"pair": "EUR_USD", "timeframe": "5m", "confidence": 0.80}
    )

    memory.add_memory(
        situation="GBP/USD showing bearish divergence, RSI overbought at 82, resistance at 1.2700",
        decision="SELL signal with 75% confidence, entry at 1.2690",
        outcome=-1.2,
        reflection="Overbought RSI alone is not sufficient; need confirmation from price action",
        metadata={"pair": "GBP_USD", "timeframe": "5m", "confidence": 0.75}
    )

    memory.add_memory(
        situation="USD/JPY ranging between 148.50-149.00, ADX below 20, no clear trend",
        decision="HOLD - no signal, waiting for breakout",
        outcome=0.0,
        reflection="Low ADX conditions require patience; premature entries in ranges often fail",
        metadata={"pair": "USD_JPY", "timeframe": "5m", "confidence": 0.0}
    )

    print(f"✅ Added 3 memories. Total: {memory.collection.count()}")

    # Test retrieval
    print("\n🔍 Testing similarity search...")
    current_situation = "EUR/USD showing bullish momentum, MACD positive, RSI at 68"
    similar = memory.get_similar_situations(current_situation, n_matches=2)

    print(f"\nCurrent situation: {current_situation}\n")
    print("Similar past situations:")
    for i, mem in enumerate(similar, 1):
        print(f"\n{i}. Distance: {mem['distance']:.3f}")
        print(f"   Reflection: {mem.get('reflection', 'N/A')}")
        print(f"   Outcome: {mem.get('outcome', 'N/A')}")

    # Show stats
    print("\n📊 Performance Statistics:")
    stats = memory.get_performance_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # Cleanup
    memory.clear()
    print("\n✓ Test complete!")


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    test_trading_memory()
