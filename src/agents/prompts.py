"""
Agent Prompt Templates
Concise prompts for search, synthesis, and validation agents
"""

from typing import List, Dict, Any


# ============================================================================
# SEARCH AGENT PROMPT
# ============================================================================

SEARCH_AGENT_PROMPT = """You are a research query generator. Generate 3-5 diverse search queries from the user's question.

Query types:
1. Broad overview query
2. Specific technical query  
3. Recent developments query
4-5. Additional complementary queries (if needed)

Return ONLY valid JSON:
{{
  "queries": ["query1", "query2", "query3", ...]
}}

User query: {user_query}
"""


def format_search_agent_prompt(user_query: str) -> str:
    """
    Format search agent prompt with user query

    Args:
        user_query: The user's research question

    Returns:
        Formatted prompt string
    """
    return SEARCH_AGENT_PROMPT.format(user_query=user_query)


# ============================================================================
# SYNTHESIS AGENT PROMPT
# ============================================================================

SYNTHESIS_AGENT_SYSTEM_PROMPT = """You are a research synthesizer. Create comprehensive research reports from retrieved sources.

Requirements:
- Cite every claim with [Source N] format
- Target length: 1200-1500 words
- Structure: Overview → Key Findings → Analysis → Conclusion
- Use clear, academic tone
- Synthesize information, don't just summarize
"""

SYNTHESIS_AGENT_USER_PROMPT = """Topic: {topic}

Sources:
{sources}

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
"""


def format_synthesis_agent_prompt(
    topic: str, sources: List[Dict[str, Any]], include_system: bool = True
) -> Dict[str, str]:
    """
    Format synthesis agent prompt with topic and sources

    Args:
        topic: Research topic/question
        sources: List of source dictionaries with 'content' and optionally 'id' or 'source_id'
        include_system: Whether to include system prompt

    Returns:
        Dictionary with 'system' and 'user' prompts (or just 'user' if include_system=False)
    """
    # Format sources as numbered list
    sources_text = "\n\n".join(
        f"[Source {i+1}]\n{sources[i].get('content', str(sources[i]))}"
        for i in range(len(sources))
    )

    user_prompt = SYNTHESIS_AGENT_USER_PROMPT.format(topic=topic, sources=sources_text)

    if include_system:
        return {"system": SYNTHESIS_AGENT_SYSTEM_PROMPT, "user": user_prompt}
    else:
        return {"user": user_prompt}


def format_synthesis_agent_messages(
    topic: str, sources: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Format synthesis agent prompt as OpenAI chat messages

    Args:
        topic: Research topic/question
        sources: List of source dictionaries with 'content'

    Returns:
        List of message dicts ready for OpenAI API
    """
    prompts = format_synthesis_agent_prompt(topic, sources, include_system=True)

    return [
        {"role": "system", "content": prompts["system"]},
        {"role": "user", "content": prompts["user"]},
    ]


# ============================================================================
# VALIDATION AGENT PROMPT
# ============================================================================

VALIDATION_AGENT_PROMPT = """You are a research report validator. Analyze the report and verify quality.

Tasks:
1. Check all [Source N] citations are valid (N matches source numbers)
2. Identify claims without citations
3. Verify citations correspond to actual sources
4. Calculate confidence score (0.0-1.0) based on:
   - Citation coverage (40%): All claims cited?
   - Citation accuracy (30%): Citations match sources?
   - Source quality (20%): Diverse, relevant sources?
   - Report structure (10%): Follows required format?

Return ONLY valid JSON:
{{
  "valid": true/false,
  "confidence": 0.0-1.0,
  "issues": ["issue1", "issue2", ...],
  "citation_coverage": 0.0-1.0,
  "unsupported_claims": ["claim1", "claim2", ...]
}}

Report:
{report}

Sources (for reference):
{sources}
"""


def format_validation_agent_prompt(report: str, sources: List[Dict[str, Any]]) -> str:
    """
    Format validation agent prompt with report and sources

    Args:
        report: The generated research report to validate
        sources: List of source dictionaries used in the report

    Returns:
        Formatted prompt string
    """
    # Format sources as numbered list
    sources_text = "\n\n".join(
        f"[Source {i+1}]\n{sources[i].get('content', str(sources[i]))}"
        for i in range(len(sources))
    )

    return VALIDATION_AGENT_PROMPT.format(report=report, sources=sources_text)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def count_sources_in_report(report: str) -> List[int]:
    """
    Extract all source citation numbers from a report

    Args:
        report: Report text with [Source N] citations

    Returns:
        List of source numbers found in the report
    """
    import re

    pattern = r"\[Source\s+(\d+)\]"
    matches = re.findall(pattern, report, re.IGNORECASE)
    return [int(m) for m in matches]


def validate_citation_range(report: str, num_sources: int) -> Dict[str, Any]:
    """
    Quick validation of citation numbers in report

    Args:
        report: Report text
        num_sources: Total number of sources available

    Returns:
        Dictionary with validation results
    """
    cited_sources = set(count_sources_in_report(report))

    invalid_citations = [n for n in cited_sources if n < 1 or n > num_sources]

    return {
        "cited_sources": sorted(cited_sources),
        "invalid_citations": invalid_citations,
        "coverage": len(cited_sources) / num_sources if num_sources > 0 else 0.0,
        "has_invalid": len(invalid_citations) > 0,
    }


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example 1: Search Agent
    user_query = "What are the latest advances in transformer architectures?"
    search_prompt = format_search_agent_prompt(user_query)
    print("=" * 70)
    print("SEARCH AGENT PROMPT")
    print("=" * 70)
    print(search_prompt)

    # Example 2: Synthesis Agent
    topic = "Transformer architectures in NLP"
    sources = [
        {"content": "Transformer models use self-attention mechanisms..."},
        {"content": "Recent work shows improved efficiency with..."},
        {"content": "The architecture enables parallel processing..."},
    ]
    synthesis_prompts = format_synthesis_agent_prompt(topic, sources)
    print("\n" + "=" * 70)
    print("SYNTHESIS AGENT PROMPT")
    print("=" * 70)
    print("System:", synthesis_prompts["system"][:100] + "...")
    print("\nUser:", synthesis_prompts["user"][:200] + "...")

    # Example 3: Validation Agent
    report = "Transformers revolutionized NLP [Source 1]. Recent improvements show better efficiency [Source 2]."
    validation_prompt = format_validation_agent_prompt(report, sources)
    print("\n" + "=" * 70)
    print("VALIDATION AGENT PROMPT")
    print("=" * 70)
    print(validation_prompt[:300] + "...")

    # Example 4: Citation validation
    validation_result = validate_citation_range(report, len(sources))
    print("\n" + "=" * 70)
    print("CITATION VALIDATION")
    print("=" * 70)
    print(validation_result)
