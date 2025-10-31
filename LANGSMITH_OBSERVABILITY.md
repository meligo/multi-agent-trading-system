# 🔍 LangSmith Observability Guide

**Status:** ✅ ENABLED
**Date:** 2025-10-28
**Project:** forex-trading-system

---

## 📋 What is LangSmith?

**LangSmith** is LangChain's observability and debugging platform. It provides:

✅ **Full Tracing** - Every LLM call, agent decision, and tool use
✅ **Performance Metrics** - Token usage, latency, cost tracking
✅ **Debugging** - Step-by-step execution visualization
✅ **Error Analysis** - Identify failures and bottlenecks
✅ **Comparison** - Compare different runs side-by-side

**Dashboard:** https://smith.langchain.com/

---

## 🚀 Quick Start

### Already Enabled!

Your system is **already configured** with LangSmith tracing. It's active right now! 🎉

Every LLM call from your agents is being automatically traced to LangSmith.

### View Your Traces

1. Go to: **https://smith.langchain.com/**
2. Sign in with your LangChain account
3. Select project: **`forex-trading-system`**
4. Browse your traces in real-time!

---

## ⚙️ Configuration

### Environment Variables (Already Set)

```bash
# In your .env file:
LANGSMITH_API_KEY=lsv2_pt_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=forex-trading-system
```

### Disable Tracing (If Needed)

To temporarily disable tracing:

```bash
# In .env, change:
LANGSMITH_TRACING=false
```

Or set environment variable:
```bash
export LANGSMITH_TRACING=false
streamlit run ig_trading_dashboard.py
```

---

## 📊 What Gets Traced

### 1. Agent Analysis Calls

**Every agent analysis is traced:**
- **PriceActionAgent** - Technical analysis reasoning
- **MomentumAgent** - Momentum assessment
- **Bull/Bear Agents** - Debate arguments
- **DecisionMaker** - Final trade decisions

**Example trace:**
```
forex_agents.generate_signal_with_details()
  ├─ PriceActionAgent.analyze()
  │   └─ LLM Call: "Analyze EUR_USD price action..."
  │       ├─ Input tokens: 1,240
  │       ├─ Output tokens: 385
  │       ├─ Latency: 2.3s
  │       └─ Response: {"has_setup": true, ...}
  │
  ├─ MomentumAgent.analyze()
  │   └─ LLM Call: "Assess EUR_USD momentum..."
  │       └─ ...
  │
  └─ InvestmentDebate.run_debate()
      ├─ BullAgent Round 1
      ├─ BearAgent Round 1
      ├─ BullAgent Round 2
      ├─ BearAgent Round 2
      └─ Judge synthesis
```

### 2. Memory Retrievals

**Memory operations are traced:**
- Similarity searches in ChromaDB
- Past lesson retrieval
- Performance stats queries

### 3. Web Intelligence

**Tavily API calls are traced:**
- Social sentiment searches
- News retrieval
- Macro context fetching

### 4. Debate System

**Full debate transcripts:**
- Each argument and rebuttal
- Judge deliberation
- Final decision synthesis

---

## 🎯 How to Use LangSmith

### Scenario 1: Debug a Bad Trade Decision

**Problem:** EUR_USD trade lost money, want to understand why.

**Steps:**
1. Go to LangSmith dashboard
2. Filter by date/time of the trade
3. Find the trace for EUR_USD signal generation
4. Click through the trace:
   - What did PriceActionAgent see?
   - What did MomentumAgent conclude?
   - What were the Bull vs Bear arguments?
   - Did any agent miss critical information?

**What to look for:**
- Did agents use all available data?
- Were there contradictions in the analysis?
- Did the debate reveal weaknesses that were ignored?
- Were there any LLM errors or hallucinations?

---

### Scenario 2: Optimize Performance

**Goal:** Reduce latency and token usage.

**Steps:**
1. View traces for 10-20 signals
2. Analyze token usage:
   - Which agents use the most tokens?
   - Are prompts too verbose?
   - Can we use gpt-4o-mini more?
3. Analyze latency:
   - Which calls are slowest?
   - Can we parallelize?
   - Are there unnecessary sequential calls?

**Optimization targets:**
- **High token users** - Shorten prompts
- **Slow calls** - Use faster models for simple tasks
- **Sequential bottlenecks** - Parallelize where possible

---

### Scenario 3: Monitor System Health

**Goal:** Ensure agents are working correctly.

**Daily checks:**
1. **Error Rate** - Any failed LLM calls?
2. **Response Quality** - Are outputs structured correctly?
3. **Consistency** - Are agents agreeing/disagreeing appropriately?
4. **Cost** - Is token usage within budget?

**Weekly checks:**
1. Compare traces week-over-week
2. Look for degradation in quality
3. Identify recurring errors
4. Track cost trends

---

### Scenario 4: Compare Two Runs

**Goal:** Test if a prompt change improved decisions.

**Steps:**
1. Make a prompt change (e.g., enhance PriceActionAgent)
2. Run a test with the same pairs
3. In LangSmith, compare the two runs:
   - Before vs After reasoning quality
   - Token usage difference
   - Confidence score changes
   - Decision agreement rate

**Example:**
```
Before prompt change:
- EUR_USD: HOLD (confidence 55%)
- Tokens: 3,240
- Reasoning: Generic

After prompt change:
- EUR_USD: BUY (confidence 78%)
- Tokens: 3,180 (cheaper!)
- Reasoning: Specific, detailed
```

---

## 🔬 Advanced Features

### 1. Filter Traces

**By agent:**
```
Filter: "tags:PriceActionAgent"
```

**By pair:**
```
Filter: "metadata.pair:EUR_USD"
```

**By decision:**
```
Filter: "metadata.signal:BUY"
```

### 2. Compare Runs

Select multiple traces and click "Compare" to see side-by-side:
- Input differences
- Output differences
- Performance metrics
- Cost analysis

### 3. Annotate Traces

Add notes to specific traces:
- "This was a great trade"
- "Agent missed key news"
- "Debate was too conservative"

Use annotations to build a knowledge base of good/bad decisions.

### 4. Export Data

Download trace data for:
- Custom analysis in Python
- Building dashboards
- Training evaluation datasets

---

## 📈 Key Metrics to Track

### 1. **Token Usage**
- **Total tokens per signal:** Target < 10,000
- **Most expensive agent:** Usually debates
- **Trend:** Should decrease as prompts optimize

### 2. **Latency**
- **Total time per signal:** Currently ~40-70s
- **Breakdown:**
  - Memory retrieval: ~0.5s
  - Tavily search: ~2-3s
  - Debates: ~30-60s
- **Target:** Keep under 2 minutes

### 3. **Error Rate**
- **LLM failures:** Target 0%
- **JSON parsing errors:** Target < 1%
- **Tool failures:** Target < 5%

### 4. **Quality Indicators**
- **Confidence scores:** Watch for trends
- **Agent agreement:** High agreement = strong signals
- **Debate intensity:** Healthy disagreement is good

---

## 🛠️ Troubleshooting

### Traces Not Appearing?

**Check 1:** Is tracing enabled?
```bash
python -c "import os; from forex_config import ForexConfig; print(f'Tracing: {os.getenv(\"LANGSMITH_TRACING\")}')"
```

**Check 2:** Is API key valid?
```bash
echo $LANGSMITH_API_KEY
# Should output: lsv2_pt_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Check 3:** Check console for LangSmith errors
```bash
# Look for errors like:
# "LangSmith API error: ..."
```

**Check 4:** Verify project name
```bash
# In LangSmith dashboard, check if project "forex-trading-system" exists
```

### Too Much Data?

**Solution 1:** Sample traces
```python
# In forex_config.py, add sampling:
import random
if random.random() < 0.1:  # Trace 10% of requests
    os.environ["LANGSMITH_TRACING"] = "true"
```

**Solution 2:** Trace only specific agents
```python
# Add conditional tracing in forex_agents.py
if pair in ["EUR_USD", "GBP_USD"]:  # Only trace majors
    # Tracing enabled
```

### High Costs?

LangSmith costs:
- **Free tier:** 5,000 traces/month
- **Beyond that:** Check LangSmith pricing

**Optimize:**
- Disable for production after debugging
- Sample traces (10-20% sufficient)
- Archive old projects

---

## 💡 Best Practices

### 1. **Use Tags**
Add tags to help filter:
```python
# In agent code, add metadata
{"tags": ["live_trading", "EUR_USD", "debate"]}
```

### 2. **Name Runs Meaningfully**
```python
# Set run name in config
os.environ["LANGSMITH_RUN_NAME"] = f"signal_{pair}_{timestamp}"
```

### 3. **Review Weekly**
- Set a recurring calendar reminder
- Review 10-20 traces each week
- Look for patterns in good/bad trades

### 4. **Document Insights**
- Keep a log of insights from LangSmith
- Share findings with team (if applicable)
- Use insights to improve prompts

### 5. **Monitor Costs**
- Check token usage trends
- Set alerts for anomalies
- Optimize expensive agents

---

## 🎓 Learning Resources

### Official Docs
- LangSmith Docs: https://docs.smith.langchain.com/
- Tracing Guide: https://docs.smith.langchain.com/tracing
- Best Practices: https://docs.smith.langchain.com/best-practices

### Video Tutorials
- LangSmith Overview: https://www.youtube.com/watch?v=...
- Debugging with LangSmith: https://www.youtube.com/watch?v=...

### Community
- Discord: LangChain Discord #langsmith channel
- GitHub: https://github.com/langchain-ai/langsmith-sdk

---

## 📊 Example: Analyzing a Complete Signal

### Trace Structure for EUR_USD Signal:

```
🎯 generate_signal_with_details (EUR_USD)
│
├─ 📊 forex_data.analyze()
│   └─ [Fetches OHLCV, indicators, S/R levels]
│
├─ 🌐 TavilyIntegration.get_comprehensive_analysis()
│   ├─ Search: "EUR_USD forex social media sentiment"
│   ├─ Search: "EUR_USD recent news"
│   └─ Search: "EUR USD macro economic context"
│
├─ 🧠 MemoryManager.get_similar_situations()
│   ├─ PriceActionAgent memory (3 similar situations)
│   └─ MomentumAgent memory (3 similar situations)
│
├─ 🤖 PriceActionAgent.analyze()
│   └─ LLM Call (gpt-4o-mini)
│       ├─ Input: Market data + Web intel + Past lessons
│       ├─ Tokens: 2,140 in / 320 out
│       ├─ Latency: 1.8s
│       └─ Output: {"has_setup": true, "direction": "BUY", "confidence": 75}
│
├─ 🤖 MomentumAgent.analyze()
│   └─ LLM Call (gpt-4o-mini)
│       ├─ Input: Momentum indicators + Past lessons
│       ├─ Tokens: 1,680 in / 280 out
│       ├─ Latency: 1.5s
│       └─ Output: {"momentum_strong": true, "direction": "UP"}
│
└─ 🎭 InvestmentDebate.run_debate()
    ├─ 🐂 BullAgent Round 1
    │   └─ LLM Call: "Present bullish case..."
    │       ├─ Tokens: 1,240 in / 180 out
    │       └─ Argument: "Strong technical setup..."
    │
    ├─ 🐻 BearAgent Round 1
    │   └─ LLM Call: "Counter with risks..."
    │       ├─ Tokens: 1,280 in / 195 out
    │       └─ Argument: "High valuation risk..."
    │
    ├─ 🐂 BullAgent Round 2 (Rebuttal)
    ├─ 🐻 BearAgent Round 2 (Rebuttal)
    │
    └─ ⚖️ Judge.synthesize()
        └─ LLM Call (gpt-4o): "Make final decision..."
            ├─ Tokens: 2,840 in / 420 out
            ├─ Latency: 3.2s
            └─ Decision: BUY (confidence: 78%)

**Total for this signal:**
- LLM Calls: 7
- Total Tokens: ~9,800 in / ~1,600 out
- Total Latency: ~45 seconds
- Total Cost: ~$0.15
```

**In LangSmith, you can:**
- Click each node to see full input/output
- See exact prompts sent to LLM
- Analyze token distribution
- Identify bottlenecks
- Debug failures

---

## ✅ Summary

**LangSmith is now ACTIVE on your system! 🎉**

**What you get:**
✅ Full observability of all agent interactions
✅ Debug bad trade decisions
✅ Optimize performance and costs
✅ Monitor system health
✅ Compare different approaches

**Next steps:**
1. **Start Trading** - LangSmith will automatically capture traces
2. **Review Dashboard** - Check https://smith.langchain.com/ daily
3. **Analyze Patterns** - Look for insights in your traces
4. **Optimize** - Use findings to improve your agents

**Your LangSmith project:** `forex-trading-system`
**Dashboard:** https://smith.langchain.com/

---

**Created:** 2025-10-28
**Status:** Active & Tracing
**Version:** 1.0
