# Multi-Agent System Documentation

Comprehensive documentation for the AI Research Assistant's multi-agent RAG workflow.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Details](#agent-details)
3. [HITL Workflow](#hitl-workflow)
4. [Configuration](#configuration)
5. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Agent Flow Diagram

```
┌─────────────┐
│ User Query  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    SEARCH AGENT                             │
│  • Query Expansion (GPT-4o Mini)                           │
│  • Semantic Search (Pinecone)                              │
│  • Result Deduplication & Ranking                          │
└──────┬──────────────────────────────────────────────────────┘
       │
       │ Updates: search_queries, search_results
       ▼
┌─────────────────────────────────────────────────────────────┐
│                  SYNTHESIS AGENT                            │
│  • Additional Pinecone Retrieval                           │
│  • Source Combination & Formatting                         │
│  • Report Generation (GPT-4o Mini)                         │
└──────┬──────────────────────────────────────────────────────┘
       │
       │ Updates: report_draft, retrieved_chunks, source_count
       ▼
┌─────────────────────────────────────────────────────────────┐
│                 VALIDATION AGENT                            │
│  • Citation Verification                                    │
│  • Quality Analysis (GPT-4o Mini)                          │
│  • Confidence Score Calculation                            │
└──────┬──────────────────────────────────────────────────────┘
       │
       │ Updates: validation_result, confidence_score, needs_hitl
       ▼
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│ needs_hitl  │  │ needs_hitl   │  │ needs_hitl   │
│   = True    │  │   = False    │  │   = False    │
└──────┬──────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ▼                 ▼                 ▼
┌─────────────┐  ┌──────────────────────────────┐
│ HITL REVIEW │  │  SET FINAL REPORT            │
│   NODE      │  │  (Auto-approve)              │
└──────┬──────┘  └──────┬───────────────────────┘
       │                 │
       └────────┬────────┘
                │
                ▼
           ┌─────────┐
           │   END   │
           └─────────┘
```

### State Management

The workflow uses a shared `ResearchState` TypedDict that is passed between all agents. This state object maintains:

- **Task Context**: `task_id`, `user_query`, `current_agent`
- **Search Results**: `search_queries`, `search_results`
- **Retrieved Data**: `retrieved_chunks`
- **Generated Content**: `report_draft`, `final_report`
- **Validation**: `validation_result`, `confidence_score`, `needs_hitl`
- **Error Handling**: `error`

#### State Schema

```python
class ResearchState(TypedDict, total=False):
    task_id: str                    # Unique task identifier
    user_query: str                 # Original user question
    search_queries: List[str]       # Generated search queries
    search_results: List[Dict]      # Raw search results from Pinecone
    retrieved_chunks: List[Dict]    # Full chunk data with metadata
    report_draft: str               # Generated report before validation
    validation_result: Dict         # Validation analysis results
    confidence_score: float         # Confidence score (0.0-1.0)
    needs_hitl: bool                # Whether human review is needed
    final_report: str               # Final approved report
    error: Optional[str]            # Error message if any
    current_agent: str              # Current agent identifier
```

#### State Flow

1. **Initial State**: Contains only `task_id`, `user_query`, and `current_agent`
2. **After Search Agent**: Populated with `search_queries` and `search_results`
3. **After Synthesis Agent**: Contains `report_draft`, `retrieved_chunks`, `source_count`
4. **After Validation Agent**: Includes `validation_result`, `confidence_score`, `needs_hitl`
5. **After HITL/Set Final**: Contains `final_report` ready for user

### LangGraph Orchestration

The workflow is built using LangGraph's `StateGraph`, which provides:

- **Node-based Architecture**: Each agent is a node in the graph
- **Conditional Routing**: Dynamic flow based on validation results
- **State Persistence**: Automatic state management between nodes
- **Error Handling**: Graceful error propagation through the graph

#### Graph Structure

```python
workflow = StateGraph(ResearchState)

# Add nodes
workflow.add_node("search", search_agent_node)
workflow.add_node("synthesis", synthesis_agent_node)
workflow.add_node("validation", validation_agent_node)
workflow.add_node("hitl_review", hitl_review_node)
workflow.add_node("set_final_report", set_final_report_node)

# Set entry point
workflow.set_entry_point("search")

# Add sequential edges
workflow.add_edge("search", "synthesis")
workflow.add_edge("synthesis", "validation")

# Conditional routing
workflow.add_conditional_edges(
    "validation",
    route_after_validation,  # Routing function
    {
        "hitl_review": "hitl_review",
        "set_final_report": "set_final_report",
    }
)

# Terminal edges
workflow.add_edge("hitl_review", END)
workflow.add_edge("set_final_report", END)
```

#### Routing Logic

The `route_after_validation` function determines the next step:

```python
def route_after_validation(state: ResearchState) -> Literal["hitl_review", "set_final_report"]:
    needs_hitl = state.get("needs_hitl", False)
    return "hitl_review" if needs_hitl else "set_final_report"
```

---

## Agent Details

### 1. Search Agent

**File**: `src/agents/search_agent.py`  
**Function**: `search_agent_node(state: ResearchState) -> ResearchState`

#### Purpose and Responsibilities

The Search Agent is responsible for:
- Expanding a single user query into multiple diverse search queries
- Performing semantic search across all queries
- Deduplicating and ranking results by relevance
- Preparing a curated set of sources for the Synthesis Agent

#### Input State Fields

- `user_query` (required): The original research question
- `task_id` (required): Task identifier for logging and cost tracking

#### Output State Fields

- `search_queries`: List of 3-5 generated search queries
- `search_results`: List of top 20 deduplicated search results
- `current_agent`: Set to `"search_agent"`

#### Prompt Design Rationale

The search agent prompt is designed to:
- Generate diverse query types (broad, specific, recent developments)
- Ensure JSON output for reliable parsing
- Balance coverage and specificity

**Prompt Template**:
```
You are a research query generator. Generate 3-5 diverse search queries from the user's question.

Query types:
1. Broad overview query
2. Specific technical query  
3. Recent developments query
4-5. Additional complementary queries (if needed)

Return ONLY valid JSON:
{
  "queries": ["query1", "query2", "query3", ...]
}

User query: {user_query}
```

#### Model Used and Parameters

- **Model**: `gpt-4o-mini`
- **Temperature**: `0.3` (balanced creativity and consistency)
- **Max Tokens**: `500` (sufficient for 3-5 queries)
- **Operation**: `"query_expansion"` (for cost tracking)

#### Error Handling Approach

1. **JSON Parsing Errors**: Attempts to extract JSON from response text
2. **Empty Queries**: Filters out empty or whitespace-only queries
3. **Pinecone Errors**: Logs errors and continues with available results
4. **API Failures**: Retries with exponential backoff (handled by OpenAIClient)

#### Example Execution

```python
# Input state
state = {
    "task_id": "task_123",
    "user_query": "What are attention mechanisms in transformers?",
    "current_agent": "search"
}

# Execute
result_state = search_agent_node(state)

# Output state
{
    "task_id": "task_123",
    "user_query": "What are attention mechanisms in transformers?",
    "search_queries": [
        "attention mechanisms transformer architecture",
        "scaled dot-product attention mechanism",
        "recent advances transformer attention",
        "self-attention mechanism deep learning",
        "multi-head attention transformer models"
    ],
    "search_results": [
        {
            "doc_id": "1706.03762",
            "title": "Attention Is All You Need",
            "score": 0.89,
            "text": "...",
            "url": "https://arxiv.org/abs/1706.03762"
        },
        # ... 19 more results
    ],
    "current_agent": "search_agent"
}
```

---

### 2. Synthesis Agent

**File**: `src/agents/synthesis_agent.py`  
**Function**: `synthesis_agent_node(state: ResearchState) -> ResearchState`

#### Purpose and Responsibilities

The Synthesis Agent:
- Retrieves additional relevant chunks from Pinecone using the user query
- Combines Pinecone chunks with search results from Search Agent
- Formats all sources into numbered citations
- Generates a comprehensive 1200-1500 word research report
- Ensures proper citation formatting throughout the report

#### Input State Fields

- `user_query` (required): Original research question
- `search_results` (required): Results from Search Agent
- `task_id` (required): Task identifier

#### Output State Fields

- `report_draft`: Generated research report with citations
- `retrieved_chunks`: List of all sources used (with full text)
- `source_count`: Total number of sources used
- `current_agent`: Set to `"synthesis"`

#### Prompt Design Rationale

The synthesis prompt uses a two-part structure:

1. **System Prompt**: Sets the role and requirements
   - Emphasizes citation requirements
   - Specifies target length and structure
   - Encourages synthesis over summarization

2. **User Prompt**: Provides context and instructions
   - Includes the research topic
   - Lists all numbered sources
   - Provides detailed structure guidelines

**System Prompt**:
```
You are a research synthesizer. Create comprehensive research reports from retrieved sources.

Requirements:
- Cite every claim with [Source N] format
- Target length: 1200-1500 words
- Structure: Overview → Key Findings → Analysis → Conclusion
- Use clear, academic tone
- Synthesize information, don't just summarize
```

**User Prompt**:
```
Topic: {topic}

Sources:
[Source 1]
{source_1_content}

[Source 2]
{source_2_content}
...

Instructions:
1. Write a comprehensive research report on the topic
2. Use all provided sources to inform your analysis
3. Cite every factual claim with [Source N] where N matches the source number
4. Follow this structure:
   - Overview (150-200 words): Context and scope
   - Key Findings (400-500 words): Main discoveries with citations
   - Analysis (400-500 words): Interpretation and implications
   - Conclusion (150-200 words): Summary and future directions
5. Word count: 1200-1500 words
6. Ensure all citations are accurate and correspond to source numbers
```

#### Model Used and Parameters

- **Model**: `gpt-4o-mini`
- **Temperature**: `0.3` (consistent, factual output)
- **Max Tokens**: `2000` (sufficient for 1200-1500 word reports)
- **Operation**: `"synthesis"` (for cost tracking)

#### Error Handling Approach

1. **Missing Chunks**: Gracefully handles S3 retrieval failures, continues with available sources
2. **Empty Sources**: Validates that at least some sources are available
3. **API Failures**: Retries with exponential backoff
4. **Citation Errors**: Logs warnings but continues (Validation Agent will catch)

#### Example Execution

```python
# Input state (after Search Agent)
state = {
    "task_id": "task_123",
    "user_query": "What are attention mechanisms in transformers?",
    "search_results": [...],  # 20 results from Search Agent
    "current_agent": "synthesis"
}

# Execute
result_state = synthesis_agent_node(state)

# Output state
{
    "task_id": "task_123",
    "user_query": "What are attention mechanisms in transformers?",
    "search_results": [...],
    "report_draft": "# Research Report: Attention Mechanisms in Transformers\n\n## Introduction\n\nAttention mechanisms have revolutionized... [Source 1] The scaled dot-product attention... [Source 2]",
    "retrieved_chunks": [
        {
            "chunk_id": "chunk_001",
            "doc_id": "1706.03762",
            "text": "Full chunk text...",
            "title": "Attention Is All You Need",
            "url": "https://arxiv.org/abs/1706.03762"
        },
        # ... more chunks
    ],
    "source_count": 25,
    "current_agent": "synthesis"
}
```

---

### 3. Validation Agent

**File**: `src/agents/validation_agent.py`  
**Function**: `validation_agent_node(state: ResearchState) -> ResearchState`

#### Purpose and Responsibilities

The Validation Agent:
- Verifies all citations are within valid range
- Analyzes report quality using GPT-4o Mini
- Checks citation coverage and accuracy
- Identifies unsupported claims and contradictions
- Calculates confidence score
- Determines if human review is needed

#### Input State Fields

- `report_draft` (required): Generated report to validate
- `retrieved_chunks` (required): List of sources used
- `task_id` (required): Task identifier

#### Output State Fields

- `validation_result`: Detailed validation analysis
  - `valid`: Boolean indicating overall validity
  - `citation_coverage`: Percentage of claims with citations
  - `invalid_citations`: List of invalid citation numbers
  - `unsupported_claims`: List of claims without citations
  - `contradictions`: List of contradictory statements
  - `issues`: List of validation issues found
- `confidence_score`: Calculated confidence (0.0-1.0)
- `needs_hitl`: Boolean flag (True if confidence < 0.7)
- `current_agent`: Set to `"validation"`

#### Prompt Design Rationale

The validation prompt:
- Requests structured JSON output for reliable parsing
- Focuses on specific validation criteria
- Provides clear examples of what to check

**Prompt Template**:
```
You are a research report validator. Analyze the following report for quality and accuracy.

Report:
{report}

Available Sources: {num_sources} sources

Validation Criteria:
1. Citation Accuracy: All [Source N] citations must reference valid sources (1-{num_sources})
2. Citation Coverage: Every factual claim should have a citation
3. Consistency: Check for contradictory statements
4. Completeness: Report should address the topic comprehensively

Return ONLY valid JSON:
{
  "valid": true/false,
  "citation_coverage": 0.0-1.0,
  "invalid_citations": [list of invalid citation numbers],
  "unsupported_claims": [list of claims without citations],
  "contradictions": [list of contradictory statements],
  "issues": [list of validation issues]
}
```

#### Model Used and Parameters

- **Model**: `gpt-4o-mini`
- **Temperature**: `0.1` (very deterministic for validation)
- **Max Tokens**: `800` (sufficient for validation results)
- **Response Format**: `{"type": "json_object"}` (ensures JSON output)
- **Operation**: `"validation"` (for cost tracking)

#### Confidence Score Calculation

The confidence score starts from the LLM's base assessment and applies deductions:

```python
confidence_score = base_score  # From LLM (0.0-1.0)

# Apply deductions
if invalid_citations:
    confidence_score -= 0.3
if len(unsupported_claims) >= 3:
    confidence_score -= 0.2
if contradictions:
    confidence_score -= 0.3

# Clamp to [0.0, 1.0]
confidence_score = max(0.0, min(1.0, confidence_score))

# Determine HITL requirement
needs_hitl = confidence_score < 0.7
```

#### Error Handling Approach

1. **Citation Verification**: Uses regex to extract and validate citations before LLM call
2. **JSON Parsing**: Attempts recovery if JSON is malformed
3. **Missing Fields**: Provides defaults for missing validation fields
4. **API Failures**: Retries with exponential backoff

#### Example Execution

```python
# Input state (after Synthesis Agent)
state = {
    "task_id": "task_123",
    "report_draft": "# Report... [Source 1] ... [Source 25]",
    "retrieved_chunks": [...],  # 25 chunks
    "current_agent": "validation"
}

# Execute
result_state = validation_agent_node(state)

# Output state
{
    "task_id": "task_123",
    "report_draft": "...",
    "retrieved_chunks": [...],
    "validation_result": {
        "valid": True,
        "citation_coverage": 0.95,
        "invalid_citations": [],
        "unsupported_claims": ["Claim about future research directions"],
        "contradictions": [],
        "issues": ["One claim lacks citation"]
    },
    "confidence_score": 0.85,
    "needs_hitl": False,
    "current_agent": "validation"
}
```

---

### 4. HITL Review Agent

**File**: `src/agents/hitl_review.py`  
**Function**: `hitl_review_node(state: ResearchState) -> ResearchState`

#### Purpose and Responsibilities

The HITL Review Agent:
- Checks if human review is required (`needs_hitl` flag)
- Displays report and validation information to user
- Prompts for user decision (Approve, Edit, Reject)
- Updates state based on user choice
- Logs review decisions

#### Input State Fields

- `needs_hitl` (required): Boolean flag indicating if review is needed
- `report_draft` (required): Report to review
- `validation_result` (required): Validation information
- `confidence_score` (required): Confidence score
- `task_id` (required): Task identifier

#### Output State Fields

- `final_report`: Approved/edited report (or empty if rejected)
- `error`: Error message if rejected (or None)
- `current_agent`: Set to `"hitl_review"`

#### Review Process

1. **Skip Check**: If `needs_hitl = False`, auto-approves and sets `final_report = report_draft`
2. **Display Information**: Shows report preview and validation details
3. **User Prompt**: Asks for action: `[A]pprove`, `[E]dit`, or `[R]eject`
4. **Process Decision**:
   - **Approve**: Sets `final_report = report_draft`
   - **Edit**: Prompts for edited text, sets `final_report = edited_text`
   - **Reject**: Sets `error = "Report rejected by human reviewer"`, `final_report = ""`

#### Error Handling Approach

1. **Console Input Errors**: Handles EOF errors gracefully (for automated testing)
2. **Empty Input**: Validates user input before processing
3. **Invalid Choices**: Prompts again for valid input

#### Example Execution

```python
# Input state (after Validation Agent, needs_hitl=True)
state = {
    "task_id": "task_123",
    "report_draft": "# Report...",
    "validation_result": {...},
    "confidence_score": 0.65,
    "needs_hitl": True,
    "current_agent": "validation"
}

# Execute (user chooses "Approve")
result_state = hitl_review_node(state)

# Output state
{
    "task_id": "task_123",
    "report_draft": "# Report...",
    "final_report": "# Report...",  # Same as draft (approved)
    "error": None,
    "current_agent": "hitl_review"
}
```

---

## HITL Workflow

### When It Triggers

The HITL (Human-In-The-Loop) review is triggered when:

```
confidence_score < 0.7
```

This threshold is configurable and can be adjusted based on:
- Quality requirements
- Risk tolerance
- Use case sensitivity

### Review Process

1. **Automatic Skip**: If `confidence_score >= 0.7`, the report is automatically approved
2. **Review Display**: If triggered, shows:
   - Report draft preview (first 1000 characters)
   - Validation information (confidence score, issues, invalid citations)
   - Confidence score breakdown
3. **User Decision**: Prompts for one of three actions:
   - `[A]pprove`: Accept the report as-is
   - `[E]dit`: Provide an edited version
   - `[R]eject`: Reject the report (triggers error flag)

### Decision Options

#### Approve
- Sets `final_report = report_draft`
- Clears any error flags
- Logs approval decision

#### Edit
- Prompts user to paste edited report text
- Validates that edited text is not empty
- Sets `final_report = edited_text`
- Logs edit decision

#### Reject
- Sets `error = "Report rejected by human reviewer. Regeneration required."`
- Sets `final_report = ""`
- Logs rejection decision
- Can trigger regeneration workflow (future enhancement)

### Future Enhancements (M4)

- Streamlit web interface for better UX
- Side-by-side comparison view
- Highlight validation issues in report
- Edit suggestions and recommendations
- Batch review capabilities

---

## Configuration

### Environment Variables

Required environment variables for the multi-agent system:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...                    # Required for all LLM calls

# Pinecone Configuration
PINECONE_API_KEY=...                     # Required for semantic search
PINECONE_INDEX_NAME=your-index-name      # Required for Pinecone queries
PINECONE_ENVIRONMENT=gcp-starter         # Optional, Pinecone environment

# AWS Configuration
S3_BUCKET_NAME=your-bucket-name          # Required for chunk retrieval
AWS_REGION=us-east-1                     # Optional, defaults to us-east-1
AWS_ACCESS_KEY_ID=...                    # Optional if using IAM roles
AWS_SECRET_ACCESS_KEY=...                # Optional if using IAM roles
```

### Model Parameters

#### Search Agent

```python
model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 500
operation = "query_expansion"
```

**Rationale**:
- Low temperature for consistent query generation
- Moderate max_tokens for 3-5 queries
- GPT-4o Mini for cost efficiency

#### Synthesis Agent

```python
model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 2000
operation = "synthesis"
```

**Rationale**:
- Low temperature for factual, consistent reports
- High max_tokens for 1200-1500 word reports
- GPT-4o Mini balances quality and cost

#### Validation Agent

```python
model = "gpt-4o-mini"
temperature = 0.1
max_tokens = 800
response_format = {"type": "json_object"}
operation = "validation"
```

**Rationale**:
- Very low temperature for deterministic validation
- Moderate max_tokens for validation results
- JSON format ensures structured output

### Cost Optimization Settings

#### Current Configuration

- **Model Selection**: GPT-4o Mini (cost-effective for all operations)
- **Token Limits**: Set to minimum required for each operation
- **Temperature**: Lower values reduce retry needs

#### Cost Breakdown (Approximate)

- **Query Expansion**: $0.0001 - $0.0002 per query
- **Embeddings**: $0.00001 - $0.00005 per query
- **Synthesis**: $0.0015 - $0.003 per report
- **Validation**: $0.0002 - $0.0005 per report
- **Total per Report**: $0.002 - $0.004

#### Optimization Strategies

1. **Caching**: Cache embeddings for repeated queries (future enhancement)
2. **Batch Processing**: Process multiple queries in parallel (future enhancement)
3. **Model Selection**: Use GPT-4o Mini for all operations (current)
4. **Token Limits**: Set appropriate max_tokens to avoid over-generation
5. **Retry Logic**: Exponential backoff reduces unnecessary API calls

### Adjustable Parameters

Key parameters that can be adjusted:

```python
# Search Agent
SEARCH_QUERY_COUNT = 3-5          # Number of queries to generate
SEARCH_TOP_K = 10                 # Results per query
SEARCH_FINAL_COUNT = 20           # Final deduplicated results

# Synthesis Agent
SYNTHESIS_TOP_K = 10              # Additional Pinecone results
SYNTHESIS_MIN_WORDS = 1200        # Minimum report length
SYNTHESIS_MAX_WORDS = 1500        # Maximum report length

# Validation Agent
CONFIDENCE_THRESHOLD = 0.7        # HITL trigger threshold
INVALID_CITATION_PENALTY = 0.3    # Confidence deduction
UNSUPPORTED_CLAIM_PENALTY = 0.2   # Confidence deduction (if 3+)
CONTRADICTION_PENALTY = 0.3       # Confidence deduction
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Search Agent Returns No Results

**Symptoms**:
- `search_results` is empty
- No queries generated

**Possible Causes**:
- Pinecone index is empty or not configured
- Invalid Pinecone API key or index name
- Query generation failed

**Solutions**:
1. Verify Pinecone index has data:
   ```python
   from src.utils.pinecone_rag import semantic_search
   results = semantic_search("test query", top_k=5)
   print(f"Found {len(results)} results")
   ```

2. Check environment variables:
   ```bash
   echo $PINECONE_API_KEY
   echo $PINECONE_INDEX_NAME
   ```

3. Check search agent logs:
   ```bash
   cat src/logs/search_agent.log
   ```

4. Verify embeddings are generated:
   ```python
   from src.utils.pinecone_rag import query_to_embedding
   embedding = query_to_embedding("test query")
   print(f"Embedding dimension: {len(embedding)}")
   ```

#### 2. Synthesis Agent Generates Short Reports

**Symptoms**:
- Report is less than 1000 words
- Missing sections

**Possible Causes**:
- Insufficient sources
- Max tokens too low
- Prompt not emphasizing length

**Solutions**:
1. Check source count:
   ```python
   print(f"Sources used: {state.get('source_count', 0)}")
   ```

2. Increase max_tokens in synthesis agent:
   ```python
   # In synthesis_agent.py
   max_tokens = 2500  # Increase from 2000
   ```

3. Verify prompt includes length requirements (already in prompt)

4. Check synthesis agent logs for warnings

#### 3. Validation Agent Reports Invalid Citations

**Symptoms**:
- Many invalid citations in validation_result
- Low confidence score

**Possible Causes**:
- Citation format mismatch
- Source numbering error
- Report has citations outside valid range

**Solutions**:
1. Verify citation format:
   ```python
   import re
   citations = re.findall(r'\[Source\s+(\d+)\]', report_draft)
   print(f"Found citations: {citations}")
   ```

2. Check source count matches:
   ```python
   num_sources = len(state.get('retrieved_chunks', []))
   print(f"Total sources: {num_sources}")
   ```

3. Review synthesis agent prompt to ensure proper citation format

4. Check validation agent logs for details

#### 4. HITL Review Not Triggering

**Symptoms**:
- Reports with low quality not going to HITL
- `needs_hitl` always False

**Possible Causes**:
- Confidence threshold too high
- Validation agent not calculating confidence correctly
- Validation result parsing error

**Solutions**:
1. Check confidence score calculation:
   ```python
   print(f"Confidence: {state.get('confidence_score', 0.0)}")
   print(f"Needs HITL: {state.get('needs_hitl', False)}")
   ```

2. Lower confidence threshold:
   ```python
   # In validation_agent.py
   needs_hitl = confidence_score < 0.6  # Lower from 0.7
   ```

3. Review validation agent logs for confidence calculation

4. Verify validation_result structure

#### 5. Cost Tracking Not Working

**Symptoms**:
- No cost records in `src/logs/cost_tracking.json`
- Cost shows as $0.00

**Possible Causes**:
- Cost tracker not initialized
- Log file path incorrect
- API calls not being tracked

**Solutions**:
1. Check cost tracking file exists:
   ```bash
   ls -la src/logs/cost_tracking.json
   ```

2. Verify cost tracker is imported:
   ```python
   from src.utils.cost_tracker import get_cost_tracker
   tracker = get_cost_tracker()
   print(f"Total cost: ${tracker.get_total_cost():.6f}")
   ```

3. Check OpenAIClient integration:
   ```python
   # Verify operation parameter is passed
   client.chat_completion(..., operation="synthesis")
   ```

4. Review cost tracking logs

#### 6. Workflow Execution Fails

**Symptoms**:
- Workflow stops at a specific agent
- Error message in state

**Possible Causes**:
- Missing required state fields
- API failures
- Network issues

**Solutions**:
1. Check state at failure point:
   ```python
   print(f"Current agent: {state.get('current_agent')}")
   print(f"Error: {state.get('error')}")
   ```

2. Review agent logs:
   ```bash
   tail -f src/logs/*.log
   ```

3. Verify all required fields are present:
   ```python
   required_fields = {
       "search": ["user_query", "task_id"],
       "synthesis": ["user_query", "search_results", "task_id"],
       "validation": ["report_draft", "retrieved_chunks", "task_id"],
   }
   ```

4. Check API connectivity:
   ```python
   from src.utils.openai_client import OpenAIClient
   client = OpenAIClient()
   # Test API call
   ```

#### 7. S3 Chunk Retrieval Fails

**Symptoms**:
- `NoSuchKey` errors in logs
- Missing chunks in retrieved_chunks

**Possible Causes**:
- Chunks not uploaded to S3
- Incorrect S3 key format
- S3 bucket permissions

**Solutions**:
1. Verify chunks exist in S3:
   ```python
   from src.utils.s3_client import S3Client
   s3 = S3Client()
   chunks = s3.list_objects(prefix="silver/chunks/")
   print(f"Found {len(chunks)} chunks")
   ```

2. Check chunk ID format:
   ```python
   chunk_id = result.get("chunk_id")
   expected_key = f"silver/chunks/{chunk_id}.json"
   ```

3. Verify S3 permissions and credentials

4. Check S3 client logs

### Debugging Tips

1. **Enable Verbose Logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Inspect State Between Agents**:
   ```python
   state = search_agent_node(state)
   print(json.dumps(state, indent=2, default=str))
   ```

3. **Test Individual Agents**:
   ```python
   # Test search agent only
   from src.agents.search_agent import search_agent_node
   result = search_agent_node(test_state)
   ```

4. **Check Cost Tracking**:
   ```python
   from src.utils.cost_tracker import get_cost_tracker
   tracker = get_cost_tracker()
   print(tracker.get_cost_by_operation())
   ```

5. **Review Log Files**:
   ```bash
   # Search agent
   tail -f src/logs/search_agent.log
   
   # Synthesis agent
   tail -f src/logs/synthesis_agent.log
   
   # Validation agent
   tail -f src/logs/validation_agent.log
   
   # HITL review
   tail -f src/logs/hitl_review.log
   ```

### Getting Help

If issues persist:

1. Check the main README.md for setup instructions
2. Review agent source code for implementation details
3. Check GitHub issues (if applicable)
4. Review cost tracking logs for API usage patterns
5. Verify all environment variables are set correctly

---

## Additional Resources

- **Main README**: `README.md` - Project overview and quick start
- **RAG Utilities**: `src/utils/pinecone_rag.py` - Vector search functions
- **Cost Tracking**: `src/utils/cost_tracker.py` - API cost monitoring
- **Workflow Runner**: `scripts/run_research_workflow.py` - CLI interface
- **Demo Script**: `scripts/demo_full_pipeline.py` - Full pipeline demonstration

---

*Last Updated: December 2024*

