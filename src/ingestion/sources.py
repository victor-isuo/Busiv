"""
Sources — Busiv
================
Nigerian fintech watchlist, regulatory bodies, and RSS feed sources.

Four signal categories:
1. Regulatory — CBN, SEC Nigeria, NDIC circulars and policy changes
2. Product     — New features, rates, partnerships, app updates
3. Market      — Funding, expansion, executive moves, strategic signals
4. Hiring      — Engineering/product surges, new offices, key departures

The regulatory layer is the enterprise hook — compliance teams at
Nigerian fintechs monitor CBN and SEC manually today. Busiv automates
that entirely.
"""

# ── Watchlist ─────────────────────────────────────────────────────────────────

FINTECH_COMPANIES = [
    "Flutterwave",
    "Moniepoint",
    "Paystack",
    "Kuda Bank",
    "Cowrywise",
    "PiggyVest",
    "Carbon Nigeria",
    "Risevest",
    "OPay",
    "PalmPay",
]

REGULATORY_BODIES = [
    "Central Bank of Nigeria",
    "CBN",
    "Securities and Exchange Commission Nigeria",
    "SEC Nigeria",
    "Nigeria Deposit Insurance Corporation",
    "NDIC",
    "Federal Competition and Consumer Protection Commission",
    "FCCPC",
]

# ── RSS Feed Sources ──────────────────────────────────────────────────────────

RSS_FEEDS = [
    # Nigerian tech and fintech news
    {
        "name":     "TechCabal",
        "url":      "https://techcabal.com/feed/",
        "category": "tech_news",
        "weight":   1.0,
    },
    {
        "name":     "Techpoint Africa",
        "url":      "https://techpoint.africa/feed/",
        "category": "tech_news",
        "weight":   1.0,
    },
    {
        "name":     "Nairametrics",
        "url":      "https://nairametrics.com/feed/",
        "category": "financial_news",
        "weight":   0.9,
    },
    {
        "name":     "The Punch Business",
        "url":      "https://punchng.com/business/feed/",
        "category": "business_news",
        "weight":   0.8,
    },
    {
        "name":     "BusinessDay",
        "url":      "https://businessday.ng/feed/",
        "category": "business_news",
        "weight":   0.85,
    },
    {
        "name":     "Disrupt Africa",
        "url":      "https://disrupt-africa.com/feed/",
        "category": "startup_news",
        "weight":   0.9,
    },
    {
        "name":     "Africa Fintech Summit",
        "url":      "https://africafintechsummit.com/feed/",
        "category": "fintech_news",
        "weight":   0.85,
    },
    # Global fintech with Africa coverage
    {
        "name":     "Finextra",
        "url":      "https://www.finextra.com/rss/headlines.aspx",
        "category": "global_fintech",
        "weight":   0.7,
    },
    {
        "name":     "TechCrunch Fintech",
        "url":      "https://techcrunch.com/category/fintech/feed/",
        "category": "global_fintech",
        "weight":   0.65,
    },
]

# ── Signal Keywords ───────────────────────────────────────────────────────────

SIGNAL_KEYWORDS = {

    "regulatory": [
        # CBN signals
        "CBN", "Central Bank of Nigeria", "monetary policy",
        "cashless policy", "foreign exchange", "forex policy",
        "banking licence", "payment service bank",
        "PSB licence", "fintech licence", "circular",
        "directive", "guideline", "regulation",
        # SEC signals
        "SEC Nigeria", "capital market", "investment platform",
        "crowdfunding", "digital asset", "crypto regulation",
        # NDIC signals
        "NDIC", "deposit insurance", "bank failure",
        "FCCPC", "consumer protection",
        # Generic regulatory
        "compliance", "penalty", "sanction", "revocation",
        "suspended", "shutdown", "crackdown",
    ],

    "product": [
        "launch", "launched", "introduces", "unveiled",
        "new feature", "new product", "card", "debit card",
        "savings", "investment", "interest rate", "returns",
        "insurance", "loan", "credit", "BNPL",
        "virtual dollar", "dollar card", "USSD",
        "merchant", "POS", "agent banking", "API",
        "partnership", "integration", "upgrade", "update",
    ],

    "market": [
        "funding", "raises", "million", "billion",
        "Series A", "Series B", "Series C", "seed round",
        "valuation", "unicorn", "acquisition", "merger",
        "expansion", "new market", "new country",
        "IPO", "listing", "investor", "venture capital",
        "CEO", "CTO", "CFO", "appointed", "joins",
        "exits", "resigns", "departure",
        "outage", "downtime", "service disruption",
    ],

    "hiring": [
        "hiring", "we are hiring", "job opening",
        "new office", "Lagos office", "Abuja office",
        "engineering roles", "product roles", "remote jobs",
        "100 engineers", "50 staff", "expansion plan",
    ],
}

# ── Relevance Scoring ─────────────────────────────────────────────────────────

def score_article_relevance(
    title: str,
    content: str,
    source_weight: float = 1.0,
) -> tuple[float, list[str], str]:
    """
    Score an article's relevance to Nigerian fintech monitoring.

    Returns:
        (score, matched_signals, primary_category)
        score: 0.0-1.0
        matched_signals: list of signal categories matched
        primary_category: highest-weight category
    """
    text = (title + " " + content).lower()

    # Check company mentions
    company_mentions = sum(
        1 for company in FINTECH_COMPANIES
        if company.lower() in text
    )

    regulatory_mentions = sum(
        1 for body in REGULATORY_BODIES
        if body.lower() in text
    )

    # Check signal keywords
    category_scores = {}
    matched = []

    for category, keywords in SIGNAL_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits > 0:
            category_scores[category] = hits
            matched.append(category)

    if not company_mentions and not regulatory_mentions and not matched:
        return 0.0, [], "none"

    # Build composite score
    company_score    = min(company_mentions * 0.25, 0.5)
    regulatory_bonus = min(regulatory_mentions * 0.15, 0.3)
    signal_score     = min(sum(category_scores.values()) * 0.05, 0.4)
    source_bonus     = (source_weight - 0.5) * 0.2

    raw_score = company_score + regulatory_bonus + signal_score + source_bonus
    final     = round(min(raw_score, 1.0), 3)

    primary = max(category_scores, key=category_scores.get) if category_scores else "general"

    return final, matched, primary




