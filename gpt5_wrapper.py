"""
GPT-5 Wrapper Module

Provides unified interface for GPT-5 access via:
1. OpenAI native client (primary)
2. MCP GPT-5 server (fallback if native unavailable)

Designed to match LangChain's ChatOpenAI interface for easy migration.
"""

import os
import json
from typing import List, Dict, Optional, Union
from openai import OpenAI, OpenAIError

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Create dummy decorator if langsmith not available
    def traceable(func):
        return func


class GPT5Message:
    """Message wrapper to match LangChain interface."""

    def __init__(self, content: str):
        self.content = content

    def __repr__(self) -> str:
        """Return string representation for LangSmith tracing."""
        return self.content

    def __str__(self) -> str:
        """Return string representation."""
        return self.content


class GPT5Wrapper:
    """
    Unified GPT-5 interface matching LangChain's ChatOpenAI pattern.

    Supports:
    - OpenAI native GPT-5 (primary)
    - MCP GPT-5 server (fallback)
    - LangChain-compatible interface
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",  # Start with gpt-4o until gpt-5 available
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: int = 60,
        reasoning_effort: str = "high"
    ):
        """
        Initialize GPT-5 wrapper.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name (gpt-5, gpt-4o, etc.)
            temperature: Temperature (0.0-2.0)
            max_tokens: Max response tokens
            timeout: Request timeout in seconds
            reasoning_effort: Reasoning effort for GPT-5 (low/medium/high)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort

        # Track which backend is being used
        self.use_openai = False
        self.use_mcp = False

        # Try to initialize OpenAI client
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, timeout=self.timeout)
                self.use_openai = True
                print(f"✅ GPT-5 Wrapper initialized with OpenAI client (model: {self.model})")
            except Exception as e:
                print(f"⚠️  OpenAI client initialization failed: {e}")
                self.use_openai = False

        # If OpenAI client failed, try MCP fallback
        if not self.use_openai:
            try:
                # Check if MCP GPT-5 tools are available
                # For now, we'll just note that MCP is available as fallback
                self.use_mcp = True
                print(f"⚠️  Falling back to MCP GPT-5 server")
            except Exception as e:
                print(f"❌ Both OpenAI and MCP initialization failed: {e}")
                raise ValueError("Cannot initialize GPT-5 wrapper - no backend available")

    @traceable(name="GPT5Wrapper.invoke", run_type="llm")
    def invoke(self, messages: Union[List, List[Dict]]) -> GPT5Message:
        """
        Invoke GPT-5 with messages (LangChain-compatible interface).

        Args:
            messages: Either:
                - List of message dicts: [{"role": "user", "content": "..."}]
                - List of LangChain messages: [HumanMessage(content="...")]

        Returns:
            GPT5Message object with .content attribute
        """
        # Convert messages to OpenAI format if needed
        formatted_messages = self._format_messages(messages)

        # Call appropriate backend
        if self.use_openai:
            content = self._invoke_openai(formatted_messages)
        elif self.use_mcp:
            content = self._invoke_mcp(formatted_messages)
        else:
            raise RuntimeError("No GPT-5 backend available")

        return GPT5Message(content)

    def _format_messages(self, messages: Union[List, List[Dict]]) -> List[Dict]:
        """
        Format messages to OpenAI format.

        Args:
            messages: Messages in various formats

        Returns:
            List of dicts with 'role' and 'content'
        """
        formatted = []

        for msg in messages:
            # If it's already a dict with role and content
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                formatted.append(msg)
            # If it's a LangChain message object
            elif hasattr(msg, 'content'):
                # Determine role from class name
                role = "user"  # Default
                if hasattr(msg, 'type'):
                    if msg.type == 'human':
                        role = "user"
                    elif msg.type == 'ai':
                        role = "assistant"
                    elif msg.type == 'system':
                        role = "system"

                formatted.append({
                    "role": role,
                    "content": msg.content
                })
            else:
                # Assume it's a simple string
                formatted.append({
                    "role": "user",
                    "content": str(msg)
                })

        return formatted

    def _invoke_openai(self, messages: List[Dict]) -> str:
        """
        Use OpenAI native client.

        Args:
            messages: Formatted message list

        Returns:
            Response content string
        """
        try:
            # Check if model supports reasoning_effort parameter (GPT-5)
            supports_reasoning = self.model.lower().startswith('gpt-5') or self.model.lower().startswith('o3')

            # Build parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # Add reasoning_effort for GPT-5/O3 models
            if supports_reasoning:
                params["reasoning_effort"] = self.reasoning_effort

            # Call API
            response = self.client.chat.completions.create(**params)

            return response.choices[0].message.content

        except OpenAIError as e:
            # If specific model not found, try fallback
            if "model not found" in str(e).lower() or "does not exist" in str(e).lower():
                print(f"⚠️  Model {self.model} not available, trying gpt-4o fallback...")

                # Try with gpt-4o
                params["model"] = "gpt-4o"
                if "reasoning_effort" in params:
                    del params["reasoning_effort"]

                try:
                    response = self.client.chat.completions.create(**params)
                    return response.choices[0].message.content
                except Exception as fallback_error:
                    print(f"❌ Fallback to gpt-4o also failed: {fallback_error}")
                    raise
            else:
                print(f"❌ OpenAI API call failed: {e}")
                raise

    def _invoke_mcp(self, messages: List[Dict]) -> str:
        """
        Use MCP GPT-5 server (fallback).

        Args:
            messages: Formatted message list

        Returns:
            Response content string
        """
        # This would call the MCP GPT-5 server
        # For now, raise NotImplementedError
        raise NotImplementedError(
            "MCP GPT-5 fallback not yet implemented. "
            "Please ensure OpenAI API key is valid and has GPT-5 access."
        )


# Test function
def test_gpt5_wrapper():
    """Test GPT-5 wrapper with sample prompt."""
    print("Testing GPT-5 Wrapper...")
    print("=" * 70)

    # Create wrapper
    try:
        wrapper = GPT5Wrapper(
            model="gpt-4o",  # Start with gpt-4o
            temperature=0.3,
            max_tokens=500,
            reasoning_effort="high"
        )

        print("\n🔍 Testing with sample forex analysis prompt...")

        # Test with simple prompt
        messages = [
            {"role": "user", "content": "Analyze this forex setup: EUR/USD showing bullish momentum with RSI at 62, MACD positive, and ADX at 32. Should we enter a BUY trade? Respond in JSON with {signal: BUY/SELL/HOLD, confidence: 0-100, reasoning: string}."}
        ]

        response = wrapper.invoke(messages)

        print("\n" + "=" * 70)
        print("RESPONSE")
        print("=" * 70)
        print(response.content)

        # Try to parse as JSON
        try:
            result = json.loads(response.content.strip().replace('```json', '').replace('```', '').strip())
            print("\n✅ Successfully parsed JSON response")
            print(f"Signal: {result.get('signal', 'N/A')}")
            print(f"Confidence: {result.get('confidence', 'N/A')}")
        except:
            print("\n⚠️  Response is not JSON (that's okay for testing)")

        print("\n" + "=" * 70)
        print("✓ GPT-5 Wrapper working!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    test_gpt5_wrapper()
