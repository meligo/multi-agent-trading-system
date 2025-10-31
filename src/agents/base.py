"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from ..core.state import AgentState
from ..core.memory import FinancialSituationMemory
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Base class for all trading system agents.

    Provides common functionality like memory access, LLM interaction,
    and tool management.
    """

    def __init__(
        self,
        name: str,
        llm: BaseChatModel,
        system_message: str,
        tools: Optional[List[BaseTool]] = None,
        memory: Optional[FinancialSituationMemory] = None,
        output_field: Optional[str] = None,
    ):
        """
        Initialize agent.

        Args:
            name: Agent name
            llm: Language model instance
            system_message: System prompt defining agent role
            tools: List of tools available to the agent
            memory: Long-term memory system
            output_field: Field in AgentState to store output
        """
        self.name = name
        self.llm = llm
        self.system_message = system_message
        self.tools = tools or []
        self.memory = memory
        self.output_field = output_field

        # Build prompt template
        self._setup_prompt()

        logger.info(f"Initialized agent '{name}' with {len(self.tools)} tools")

    def _setup_prompt(self) -> None:
        """Setup the prompt template for this agent."""
        messages = [
            ("system", self._build_system_prompt()),
            MessagesPlaceholder(variable_name="messages"),
        ]

        self.prompt = ChatPromptTemplate.from_messages(messages)

        # Bind tools to LLM if available
        if self.tools:
            tool_names = [tool.name for tool in self.tools]
            self.prompt = self.prompt.partial(tool_names=", ".join(tool_names))
            self.chain = self.prompt | self.llm.bind_tools(self.tools)
        else:
            self.chain = self.prompt | self.llm

    def _build_system_prompt(self) -> str:
        """Build the complete system prompt."""
        base_prompt = (
            "You are a helpful AI assistant, collaborating with other assistants. "
            "Use the provided tools to progress towards answering the question. "
            "If you are unable to fully answer, that's OK; another assistant with different tools "
            "will help where you left off. Execute what you can to make progress."
        )

        if self.tools:
            base_prompt += "\nYou have access to the following tools: {tool_names}."

        base_prompt += f"\n\n{self.system_message}"
        base_prompt += "\n\nFor your reference, the current date is {{current_date}}. "
        base_prompt += "The company we want to look at is {{ticker}}."

        return base_prompt

    def get_memories(self, state: AgentState) -> str:
        """
        Retrieve relevant memories for current situation.

        Args:
            state: Current agent state

        Returns:
            Formatted string of past lessons
        """
        if not self.memory:
            return "No past memories available."

        # Build situation summary
        situation = self._build_situation_summary(state)

        # Retrieve memories
        memories = self.memory.get_memories(situation, n_matches=3)

        if not memories:
            return "No relevant past memories found."

        # Format memories
        formatted = "\n".join([
            f"- [{mem.get('similarity', 0):.2f}] {mem['recommendation']}"
            for mem in memories
        ])

        return f"Relevant lessons from past situations:\n{formatted}"

    def _build_situation_summary(self, state: AgentState) -> str:
        """Build a summary of the current situation for memory retrieval."""
        parts = []

        if hasattr(state, "market_report") and state.market_report:
            parts.append(f"Market: {state.market_report[:200]}")
        if hasattr(state, "sentiment_report") and state.sentiment_report:
            parts.append(f"Sentiment: {state.sentiment_report[:200]}")
        if hasattr(state, "news_report") and state.news_report:
            parts.append(f"News: {state.news_report[:200]}")
        if hasattr(state, "fundamentals_report") and state.fundamentals_report:
            parts.append(f"Fundamentals: {state.fundamentals_report[:200]}")

        return " | ".join(parts) if parts else "No context available"

    def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Execute the agent's logic.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        try:
            # Prepare prompt with current context
            prompt_with_data = self.prompt.partial(
                current_date=state["trade_date"],
                ticker=state["company_of_interest"]
            )

            # Invoke the chain
            result = prompt_with_data.invoke(state["messages"])

            # Extract output
            output = {}
            output["messages"] = [result]

            # If no tool calls, extract final output
            if not getattr(result, "tool_calls", None):
                if self.output_field:
                    output[self.output_field] = result.content
                output["sender"] = self.name

            logger.debug(f"Agent '{self.name}' produced output")

            return output

        except Exception as e:
            logger.error(f"Agent '{self.name}' failed: {e}", exc_info=True)
            raise

    @abstractmethod
    def create_node(self):
        """
        Create a LangGraph node function for this agent.

        Returns:
            Callable that can be used as a LangGraph node
        """
        def node(state: AgentState) -> Dict[str, Any]:
            return self.invoke(state)

        return node

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', tools={len(self.tools)})"
