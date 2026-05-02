"""
Feed Ingestor — Busiv
======================
Pulls articles from RSS feeds, scores relevance, deduplicates
via SHA256, and stores relevant items in ChromaDB.

Why SHA256 deduplication:
The same article appears across multiple feeds and multiple runs.
Without deduplication the synthesis agent sees the same story
five times and thinks it is five separate developments. SHA256
of the article URL is a reliable unique identifier that survives
title reformatting and content updates.

Why relevance scoring before storage:
A Nigerian fintech intelligence system should not store
articles about European banking regulation or US tech layoffs.
Only articles that mention watched companies, regulatory bodies,
or domain-specific signals get indexed. This keeps the ChromaDB
store focused and the synthesis agent's retrieval precise.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

from src.ingestion.sources import RSS_FEEDS, score_article_relevance

logger = logging.getLogger(__name__)

RELEVANCE_THRESHOLD = 0.15  # articles below this score are discarded
MAX_CONTENT_LENGTH  = 2000  # chars of article body to store
CHROMA_PATH         = Path("data/busiv_store")
COLLECTION_NAME     = "nigerian_fintech_intelligence"


# ── ChromaDB setup ────────────────────────────────────────────────────────────

def get_vectorstore():
    """Initialise or load the Busiv ChromaDB collection."""
    from langchain_chroma import Chroma
    from langchain_community.embeddings import SentenceTransformerEmbeddings

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_PATH),
    )


# ── Article parsing ───────────────────────────────────────────────────────────

def _extract_content(entry: feedparser.FeedParserDict) -> str:
    """Extract readable text from a feed entry."""
    # Try content field first, then summary
    if hasattr(entry, "content") and entry.content:
        raw = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        raw = entry.summary
    else:
        raw = ""

    if raw:
        soup = BeautifulSoup(raw, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        return text[:MAX_CONTENT_LENGTH]

    return ""


def _article_id(url: str) -> str:
    """SHA256 of URL — stable unique identifier for deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_date(entry: feedparser.FeedParserDict) -> str:
    """Extract publication date from feed entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return datetime.utcnow().isoformat()


# ── Deduplication ─────────────────────────────────────────────────────────────

def _already_stored(vectorstore, article_id: str) -> bool:
    """Check if an article is already in the store."""
    try:
        existing = vectorstore.get(where={"article_id": article_id})
        return bool(existing and existing.get("ids"))
    except Exception:
        return False


# ── Feed fetching ─────────────────────────────────────────────────────────────

def _fetch_feed(feed_config: dict) -> list[dict]:
    """
    Fetch and parse a single RSS feed.
    Returns list of article dicts.
    """
    articles = []
    name     = feed_config["name"]
    url      = feed_config["url"]
    weight   = feed_config.get("weight", 1.0)

    try:
        logger.info(f"Fetching: {name}")
        # Use httpx with timeout — feedparser can hang on slow feeds
        resp = httpx.get(url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "Busiv/1.0 (intelligence@busiv.ai)"})
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)

        for entry in feed.entries[:20]:  # cap at 20 per feed per run
            try:
                url_  = getattr(entry, "link", "")
                title = getattr(entry, "title", "No title")

                if not url_:
                    continue

                content    = _extract_content(entry)
                article_id = _article_id(url_)
                pub_date   = _parse_date(entry)

                score, signals, primary_category = score_article_relevance(
                    title, content, weight
                )

                if score >= RELEVANCE_THRESHOLD:
                    articles.append({
                        "article_id":       article_id,
                        "title":            title,
                        "url":              url_,
                        "source":           name,
                        "content":          content,
                        "published_at":     pub_date,
                        "relevance_score":  score,
                        "signal_categories": signals,
                        "primary_category": primary_category,
                        "ingested_at":      datetime.utcnow().isoformat(),
                    })

            except Exception as e:
                logger.warning(f"Entry parse error in {name}: {e}")
                continue

        logger.info(f"{name}: {len(articles)} relevant articles")

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {name} — skipping")
    except Exception as e:
        logger.error(f"Failed to fetch {name}: {e}")

    return articles


# ── Main ingestion function ───────────────────────────────────────────────────

def run_ingestion(vectorstore=None) -> dict:
    """
    Run a complete ingestion cycle across all RSS feeds.

    1. Fetch all configured feeds
    2. Score each article for relevance
    3. Deduplicate against existing store
    4. Store new relevant articles in ChromaDB

    Returns summary dict with counts.
    """
    logger.info("Starting ingestion cycle")
    start = time.time()

    if vectorstore is None:
        vectorstore = get_vectorstore()

    all_articles    = []
    new_count       = 0
    duplicate_count = 0
    low_score_count = 0

    # Fetch all feeds
    for feed_config in RSS_FEEDS:
        articles = _fetch_feed(feed_config)
        all_articles.extend(articles)
        time.sleep(0.5)  # polite crawl delay between feeds

    logger.info(f"Fetched {len(all_articles)} relevant articles across all feeds")

    # Deduplicate and store
    from langchain_core.documents import Document

    for article in all_articles:
        article_id = article["article_id"]

        if _already_stored(vectorstore, article_id):
            duplicate_count += 1
            continue

        # Build document text for embedding
        doc_text = (
            f"TITLE: {article['title']}\n"
            f"SOURCE: {article['source']}\n"
            f"DATE: {article['published_at']}\n"
            f"SIGNALS: {', '.join(article['signal_categories'])}\n"
            f"URL: {article['url']}\n\n"
            f"CONTENT: {article['content']}"
        )

        doc = Document(
            page_content=doc_text,
            metadata={
                "article_id":       article["article_id"],
                "title":            article["title"][:200],
                "url":              article["url"],
                "source":           article["source"],
                "published_at":     article["published_at"],
                "relevance_score":  article["relevance_score"],
                "primary_category": article["primary_category"],
                "ingested_at":      article["ingested_at"],
            }
        )

        try:
            vectorstore.add_documents([doc])
            new_count += 1
        except Exception as e:
            logger.error(f"Failed to store article {article_id}: {e}")

    elapsed = round(time.time() - start, 2)

    summary = {
        "run_at":        datetime.utcnow().isoformat(),
        "feeds_checked": len(RSS_FEEDS),
        "articles_found": len(all_articles),
        "new_stored":    new_count,
        "duplicates":    duplicate_count,
        "elapsed_s":     elapsed,
    }

    logger.info(
        f"Ingestion complete in {elapsed}s — "
        f"New: {new_count} | Duplicates: {duplicate_count}"
    )

    return summary


def get_recent_articles(
    vectorstore,
    hours: int = 24,
    limit: int = 40,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve articles from the last N hours for synthesis.

    Args:
        vectorstore: ChromaDB instance
        hours:       How far back to look
        limit:       Max articles to return
        category:    Optional filter by signal category

    Returns:
        List of article dicts sorted by relevance score
    """
    from datetime import timedelta

    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    try:
        where_filter: dict = {"ingested_at": {"$gt": cutoff}}
        if category:
            where_filter["primary_category"] = category

        results = vectorstore.get(
            where=where_filter,
            limit=limit,
            include=["documents", "metadatas"],
        )

        articles = []
        docs      = results.get("documents", []) or []
        metas     = results.get("metadatas", []) or []

        for doc, meta in zip(docs, metas):
            articles.append({
                "content":  doc,
                "metadata": meta,
            })

        # Sort by relevance score descending
        articles.sort(
            key=lambda x: x["metadata"].get("relevance_score", 0),
            reverse=True
        )

        return articles

    except Exception as e:
        logger.error(f"Article retrieval failed: {e}")
        return []

