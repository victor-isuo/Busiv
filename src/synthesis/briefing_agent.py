"""
Briefing Agent — Busiv
========================
LangGraph synthesis agent that reasons across ingested articles
and produces a structured Nigerian fintech intelligence briefing.

Why LangGraph here not CrewAI:
This is a single-agent stateful workflow, not a role-based
sequential handoff. The agent needs to:
1. Query the store for recent articles
2. Reason across them to detect patterns
3. Structure findings by signal category
4. Cite every finding to its source article

LangGraph's explicit state machine is the right tool for
a pipeline with defined steps and structured output requirements.
CrewAI adds role overhead that a single-agent synthesis task
does not need.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import TypedDict, Annotated
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_groq import ChatGroq
from langchain_core.documents import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────

class BriefingState(TypedDict):
    articles:        list[dict]
    article_count:   int
    raw_synthesis:   str
    briefing:        dict
    error:           str


# ── LLM ──────────────────────────────────────────────────────────────────────

def get_llm():
    return ChatGroq(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.1,
        max_tokens=4096,
    )


# ── Node: Load articles ───────────────────────────────────────────────────────

def load_articles_node(state: BriefingState) -> BriefingState:
    """Articles are already loaded into state before graph runs."""
    articles = state.get("articles", [])
    logger.info(f"Synthesis: processing {len(articles)} articles")
    return {**state, "article_count": len(articles)}


# ── Node: Synthesise ──────────────────────────────────────────────────────────

def synthesise_node(state: BriefingState) -> BriefingState:
    """
    Core synthesis — LLM reasons across all articles and
    produces structured findings by signal category.
    """
    articles = state["articles"]
    if not articles:
        return {**state, "raw_synthesis": "", "error": "No articles to synthesise"}

    # Format articles for the prompt
    articles_text = ""
    for i, article in enumerate(articles[:30], 1):  # cap at 30 articles
        meta    = article.get("metadata", {})
        content = article.get("content", "")
        articles_text += (
            f"\n[ARTICLE {i}]\n"
            f"Title: {meta.get('title', 'No title')}\n"
            f"Source: {meta.get('source', 'Unknown')}\n"
            f"Date: {meta.get('published_at', 'Unknown')[:10]}\n"
            f"Signal: {meta.get('primary_category', 'general')}\n"
            f"URL: {meta.get('url', '')}\n"
            f"Content: {content[:800]}\n"
        )

    today = datetime.utcnow().strftime("%B %d, %Y")

    system_prompt = """You are a Senior Intelligence Analyst specialising in Nigerian fintech.
You produce structured daily briefings for executives, investors, and compliance officers.

Your briefing must:
1. Group findings by signal category: REGULATORY, PRODUCT, MARKET, HIRING
2. Within each category, identify the most significant developments
3. Cite the article number [ARTICLE N] and source for every finding
4. Highlight any CBN/SEC regulatory changes as PRIORITY items
5. Note any patterns — multiple companies doing the same thing, regulatory pressure building
6. Write concisely — executives read fast

Format your response as valid JSON following the exact schema provided."""

    user_prompt = f"""Today is {today}.

Analyse these {len(articles)} Nigerian fintech intelligence articles
and produce a structured briefing.

ARTICLES:
{articles_text}

Return a JSON object with this EXACT schema:
{{
  "date": "{today}",
  "headline": "One sentence capturing the most important development today",
  "executive_summary": "3-4 sentences summarising the day's most significant movements",
  "priority_alert": {{
    "has_alert": true or false,
    "alert_type": "regulatory" or "market" or "product" or null,
    "alert_text": "One sentence describing the urgent development, or null"
  }},
  "sections": {{
    "regulatory": {{
      "has_content": true or false,
      "summary": "2-3 sentences on regulatory developments",
      "findings": [
        {{
          "title": "Short finding title",
          "detail": "2-3 sentence explanation",
          "companies_mentioned": ["Company1", "Company2"],
          "citation": "[ARTICLE N] Source Name",
          "url": "article url",
          "significance": "HIGH or MEDIUM or LOW"
        }}
      ]
    }},
    "product": {{
      "has_content": true or false,
      "summary": "2-3 sentences",
      "findings": []
    }},
    "market": {{
      "has_content": true or false,
      "summary": "2-3 sentences",
      "findings": []
    }},
    "hiring": {{
      "has_content": true or false,
      "summary": "2-3 sentences",
      "findings": []
    }}
  }},
  "companies_active_today": ["list of companies mentioned in today's articles"],
  "article_count": {len(articles)},
  "sources_used": ["list of source names used"]
}}

Return ONLY the JSON object. No markdown. No explanation."""

    try:
        llm      = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw = response.content.strip()
        return {**state, "raw_synthesis": raw}

    except Exception as e:
        logger.error(f"Synthesis LLM call failed: {e}")
        return {**state, "raw_synthesis": "", "error": str(e)}


# ── Node: Parse output ────────────────────────────────────────────────────────

def parse_output_node(state: BriefingState) -> BriefingState:
    """Parse the LLM's JSON output into a structured briefing dict."""
    raw = state.get("raw_synthesis", "")

    if not raw:
        return {**state, "briefing": {}, "error": state.get("error", "Empty synthesis")}

    try:
        # Strip markdown fences if present
        clean = raw
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        briefing = json.loads(clean)

        # Add metadata
        briefing["generated_at"]  = datetime.utcnow().isoformat()
        briefing["article_count"] = state.get("article_count", 0)

        logger.info(
            f"Briefing parsed — "
            f"Sections: {sum(1 for s in briefing.get('sections', {}).values() if s.get('has_content'))}/4 | "
            f"Priority alert: {briefing.get('priority_alert', {}).get('has_alert', False)}"
        )

        return {**state, "briefing": briefing}

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}\nRaw: {raw[:500]}")
        # Return minimal valid briefing
        fallback = {
            "date":              datetime.utcnow().strftime("%B %d, %Y"),
            "headline":          "Nigerian Fintech Intelligence Briefing",
            "executive_summary": raw[:500],
            "priority_alert":    {"has_alert": False},
            "sections":          {},
            "article_count":     state.get("article_count", 0),
            "generated_at":      datetime.utcnow().isoformat(),
            "parse_error":       str(e),
        }
        return {**state, "briefing": fallback}


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_synthesis_graph():
    """Build the LangGraph synthesis pipeline."""
    graph = StateGraph(BriefingState)

    graph.add_node("load_articles", load_articles_node)
    graph.add_node("synthesise",    synthesise_node)
    graph.add_node("parse_output",  parse_output_node)

    graph.set_entry_point("load_articles")
    graph.add_edge("load_articles", "synthesise")
    graph.add_edge("synthesise",    "parse_output")
    graph.add_edge("parse_output",  END)

    return graph.compile()


# ── Main entry point ──────────────────────────────────────────────────────────

async def generate_briefing(
    vectorstore,
    hours: int = 24,
) -> dict:
    """
    Generate a structured Nigerian fintech intelligence briefing
    from articles ingested in the last N hours.

    Args:
        vectorstore: ChromaDB instance with ingested articles
        hours:       Lookback window in hours

    Returns:
        Structured briefing dict
    """
    from src.ingestion.feed_ingestor import get_recent_articles

    logger.info(f"Generating briefing from last {hours}h articles")
    start = time.time()

    articles = get_recent_articles(vectorstore, hours=hours, limit=40)

    if not articles:
        logger.warning("No articles found for briefing window")
        return {
            "date":          datetime.utcnow().strftime("%B %d, %Y"),
            "headline":      "No new intelligence available",
            "article_count": 0,
            "generated_at":  datetime.utcnow().isoformat(),
        }

    graph = build_synthesis_graph()
    result = graph.invoke({
        "articles":      articles,
        "article_count": len(articles),
        "raw_synthesis": "",
        "briefing":      {},
        "error":         "",
    })

    briefing = result.get("briefing", {})
    elapsed  = round(time.time() - start, 2)
    logger.info(f"Briefing generated in {elapsed}s")

    return briefing






