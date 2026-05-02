"""
Scheduler — Busiv
==================
APScheduler configuration for autonomous pipeline execution.

Two scheduled jobs:

1. Ingestion job — runs every 6 hours
   Fetches all RSS feeds, scores relevance, deduplicates,
   stores new articles. No LLM calls. Fast. Always on.

2. Synthesis + Delivery job — runs once daily at 07:00 Lagos time
   Queries the ChromaDB store for last 24 hours of articles,
   runs the LangGraph synthesis agent, generates the briefing,
   delivers via dashboard and email.

Why separate schedules:
Ingestion is cheap — no LLM calls, just HTTP and vector storage.
Running it every 6 hours means the store is always fresh.
Synthesis is expensive — LLM calls, structured reasoning.
Running it once daily at 07:00 delivers the briefing when
Lagos professionals start their day.

This is what "autonomous" means — the system runs while you sleep
and the briefing is waiting when you wake up.
"""

import logging
import os
from dotenv import load_dotenv
load_dotenv()

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None
_vectorstore = None


def set_vectorstore(vs):
    global _vectorstore
    _vectorstore = vs


async def _run_ingestion_job():
    """Scheduled ingestion — every 6 hours."""
    logger.info("Scheduled ingestion job starting")
    try:
        from src.ingestion.feed_ingestor import run_ingestion
        summary = run_ingestion(_vectorstore)
        logger.info(
            f"Ingestion job complete — "
            f"New articles: {summary['new_stored']} | "
            f"Duplicates: {summary['duplicates']}"
        )
    except Exception as e:
        logger.error(f"Ingestion job failed: {e}", exc_info=True)


async def _run_synthesis_job():
    """Scheduled synthesis + delivery — daily at 07:00 Lagos time."""
    logger.info("Scheduled synthesis + delivery job starting")
    try:
        from src.synthesis.briefing_agent import generate_briefing
        from src.delivery.email_sender import deliver_briefing
        from src.delivery.report_store import save_briefing

        # Generate briefing from last 24h articles
        briefing = await generate_briefing(_vectorstore, hours=24)

        if not briefing or briefing.get("article_count", 0) == 0:
            logger.info("No new relevant articles in last 24h — skipping delivery")
            return

        # Save to dashboard store
        report_id = save_briefing(briefing)
        logger.info(f"Briefing saved — ID: {report_id}")

        # Email delivery
        email_to = os.getenv("EMAIL_TO", "")
        if email_to:
            await deliver_briefing(briefing, email_to)
            logger.info(f"Briefing delivered to {email_to}")
        else:
            logger.warning("EMAIL_TO not set — skipping email delivery")

        logger.info("Synthesis + delivery job complete")

    except Exception as e:
        logger.error(f"Synthesis job failed: {e}", exc_info=True)


def start_scheduler(vectorstore) -> AsyncIOScheduler:
    """
    Start the Busiv autonomous pipeline scheduler.

    Returns the running scheduler instance.
    """
    global _scheduler, _vectorstore
    _vectorstore = vectorstore

    _scheduler = AsyncIOScheduler(timezone="Africa/Lagos")

    # Ingestion — every 6 hours
    _scheduler.add_job(
        _run_ingestion_job,
        trigger=IntervalTrigger(hours=6),
        id="ingestion",
        name="Feed Ingestion",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Synthesis + delivery — daily at 07:00 Lagos time
    hour = int(os.getenv("PIPELINE_SCHEDULE_HOUR", "7"))
    minute = int(os.getenv("PIPELINE_SCHEDULE_MINUTE", "0"))

    _scheduler.add_job(
        _run_synthesis_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="synthesis_delivery",
        name="Synthesis and Delivery",
        replace_existing=True,
        misfire_grace_time=600,
    )

    _scheduler.start()

    logger.info(
        f"Busiv scheduler started — "
        f"Ingestion: every 6h | "
        f"Synthesis: daily at {hour:02d}:{minute:02d} Lagos time"
    )

    return _scheduler


def stop_scheduler():
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """Return current scheduler status for the dashboard."""
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })

    return {"running": True, "jobs": jobs}


async def trigger_ingestion_now() -> dict:
    """Manually trigger an ingestion run — callable from API."""
    logger.info("Manual ingestion triggered")
    await _run_ingestion_job()
    return {"triggered": "ingestion", "status": "complete"}


async def trigger_synthesis_now() -> dict:
    """Manually trigger synthesis + delivery — callable from API."""
    logger.info("Manual synthesis triggered")
    await _run_synthesis_job()
    return {"triggered": "synthesis", "status": "complete"}

