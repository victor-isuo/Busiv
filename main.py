"""
Busiv — Nigerian Fintech Intelligence Platform
================================================
FastAPI application with scheduled autonomous pipeline.

Endpoints:
  GET  /           — Dashboard UI
  GET  /health     — System health
  GET  /briefings  — Recent briefings list
  GET  /briefings/latest       — Latest briefing
  GET  /briefings/{report_id}  — Specific briefing
  POST /trigger/ingestion      — Manual ingestion trigger
  POST /trigger/synthesis      — Manual synthesis trigger
  GET  /scheduler/status       — Scheduler job status
  GET  /store/stats            — ChromaDB store statistics
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

vectorstore = None
is_ready    = False


async def startup():
    global vectorstore, is_ready
    try:
        logger.info("Initialising Busiv store...")
        from src.ingestion.feed_ingestor import get_vectorstore
        vectorstore = get_vectorstore()

        logger.info("Starting autonomous pipeline scheduler...")
        from src.ingestion.scheduler import start_scheduler, set_vectorstore
        set_vectorstore(vectorstore)
        start_scheduler(vectorstore)

        # Run initial ingestion immediately on startup
        logger.info("Running startup ingestion...")
        from src.ingestion.feed_ingestor import run_ingestion
        summary = run_ingestion(vectorstore)
        logger.info(f"Startup ingestion complete — {summary['new_stored']} articles stored")

        is_ready = True
        logger.info("Busiv ready.")

    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(startup())
    yield
    from src.ingestion.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("Busiv shutdown complete.")


app = FastAPI(
    title="Busiv",
    description="Autonomous Nigerian Fintech Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    from src.ingestion.scheduler import get_scheduler_status
    return {
        "status":     "healthy",
        "ready":      is_ready,
        "scheduler":  get_scheduler_status(),
        "store":      vectorstore is not None,
    }


@app.get("/briefings")
async def list_briefings(limit: int = 20):
    from src.delivery.report_store import load_briefings
    briefings = load_briefings(limit=limit)
    # Return summary only — not full content
    summaries = []
    for b in briefings:
        summaries.append({
            "report_id":     b.get("report_id"),
            "date":          b.get("date"),
            "headline":      b.get("headline"),
            "article_count": b.get("article_count", 0),
            "has_alert":     b.get("priority_alert", {}).get("has_alert", False),
            "generated_at":  b.get("generated_at"),
        })
    return {"briefings": summaries, "total": len(summaries)}


@app.get("/briefings/latest")
async def latest_briefing():
    from src.delivery.report_store import load_latest_briefing
    briefing = load_latest_briefing()
    if not briefing:
        raise HTTPException(status_code=404, detail="No briefings generated yet.")
    return briefing


@app.get("/briefings/{report_id}")
async def get_briefing(report_id: str):
    from src.delivery.report_store import load_briefing_by_id
    briefing = load_briefing_by_id(report_id)
    if not briefing:
        raise HTTPException(status_code=404, detail=f"Briefing '{report_id}' not found.")
    return briefing


@app.post("/trigger/ingestion")
async def trigger_ingestion(background_tasks: BackgroundTasks):
    """Manually trigger an ingestion cycle."""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Busiv is still initialising.")

    async def _run():
        from src.ingestion.feed_ingestor import run_ingestion
        summary = run_ingestion(vectorstore)
        logger.info(f"Manual ingestion complete — {summary}")

    background_tasks.add_task(_run)
    return {"triggered": "ingestion", "note": "Running in background."}


@app.post("/trigger/synthesis")
async def trigger_synthesis(background_tasks: BackgroundTasks):
    """Manually trigger synthesis + delivery."""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Busiv is still initialising.")

    async def _run():
        from src.synthesis.briefing_agent import generate_briefing
        from src.delivery.report_store import save_briefing
        from src.delivery.email_sender import deliver_briefing

        briefing = await generate_briefing(vectorstore, hours=24)
        if briefing.get("article_count", 0) == 0:
            logger.info("No articles for synthesis")
            return

        save_briefing(briefing)

        email_to = os.getenv("EMAIL_TO", "")
        if email_to:
            await deliver_briefing(briefing, email_to)

    background_tasks.add_task(_run)
    return {
        "triggered": "synthesis",
        "note":      "Running in background. Check /briefings/latest in ~60s."
    }


@app.get("/scheduler/status")
async def scheduler_status():
    from src.ingestion.scheduler import get_scheduler_status
    return get_scheduler_status()


@app.get("/store/stats")
async def store_stats():
    """Return ChromaDB store statistics."""
    if not vectorstore:
        return {"error": "Store not initialised"}
    try:
        data = vectorstore.get(include=["metadatas"])
        metas = data.get("metadatas") or []
        sources = {}
        categories = {}
        for m in metas:
            s = m.get("source", "Unknown")
            c = m.get("primary_category", "general")
            sources[s]     = sources.get(s, 0) + 1
            categories[c]  = categories.get(c, 0) + 1
        return {
            "total_articles": len(metas),
            "sources":        sources,
            "categories":     categories,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)

