# Migration Quick Reference

## What Changed (TL;DR)

### Before
```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class Agent:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def analyze(self, data):
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content
```

### After
```python
from gpt5_wrapper import GPT5Wrapper

class Agent:
    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm

    def analyze(self, data):
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return response.content
```

## Testing

### Quick Test
```bash
python test_migration.py
```

### Full Test (requires IG API)
```bash
python forex_agents.py
```

## Agents Migrated

| Agent | File | Line |
|-------|------|------|
| PriceActionAgent | forex_agents.py | 18, 171 |
| MomentumAgent | forex_agents.py | 205, 318 |
| DecisionMaker | forex_agents.py | 494, 541 |
| ForexTradingSystem | forex_agents.py | 577-584 |

## Key Changes

1. **Import**: `ChatOpenAI` → `GPT5Wrapper`
2. **Message**: `HumanMessage(content=x)` → `{"role": "user", "content": x}`
3. **Parameter**: Added `reasoning_effort="high"`
4. **API Key**: Now explicit in initialization

## What's Preserved

- ✅ All error handling
- ✅ All JSON parsing
- ✅ All fallback responses
- ✅ All technical indicators
- ✅ All calculation logic

## Status

✅ **COMPLETE & VERIFIED**

All agents working with GPT5Wrapper, fully tested, production ready.
