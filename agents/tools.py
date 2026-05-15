"""
Module 7 — Agent Tools
Functions decorated with @tool that agents can call.
Each tool is a plain async Python function — keep them focused and testable.
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(fn):
        return fn


@tool
async def rag_search(query: str, category: str | None = None, year: int | None = None) -> str:
    """
    Search the ArXiv knowledge base for relevant papers.

    Args:
        query: Natural language search query
        category: Optional ArXiv category filter (e.g. 'cs.AI', 'cs.LG')
        year: Optional year filter

    Returns:
        Formatted string of relevant chunks with paper IDs and titles.
    """
    from rag.pipeline import RAGPipeline

    filters: dict = {}
    if category:
        filters["category"] = category
    if year:
        filters["year"] = year

    rag = RAGPipeline()
    response = await rag.query(query, filters=filters or None)

    if not response.chunks_used:
        return "No relevant papers found."

    lines: list[str] = []
    for i, chunk in enumerate(response.chunks_used, 1):
        lines.append(f"[{i}] {chunk.title} ({chunk.paper_id}, score={chunk.score:.3f})")
        lines.append(chunk.text[:500])
        lines.append("")
    return "\n".join(lines)


@tool
async def paper_metadata(paper_id: str) -> str:
    """
    Fetch structured metadata for a specific ArXiv paper.

    Args:
        paper_id: ArXiv paper ID (e.g. '1706.03762')

    Returns:
        JSON string with title, authors, abstract, date, category.
    """
    import asyncpg

    db_url = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")
    conn = None
    try:
        conn = await asyncpg.connect(db_url, timeout=5.0)
        row = await conn.fetchrow(
            "SELECT id, title, authors, abstract, published_date, category "
            "FROM papers WHERE id = $1",
            paper_id,
        )
        if row is None:
            return json.dumps({"error": f"Paper {paper_id!r} not found"})
        return json.dumps({
            "paper_id": row["id"],
            "title": row["title"],
            "authors": row["authors"],
            "abstract": row["abstract"],
            "published_date": str(row["published_date"]),
            "category": row["category"],
        })
    except Exception as e:
        logger.warning("paper_metadata failed for %s: %s", paper_id, e)
        return json.dumps({"error": str(e)})
    finally:
        if conn is not None:
            await conn.close()


@tool
async def semantic_compare(paper_id_a: str, paper_id_b: str) -> str:
    """
    Compare two ArXiv papers by embedding their abstracts and computing cosine similarity.

    Returns:
        Similarity score + a brief summary of key differences.
    """
    import asyncpg
    from ingestion.embedder import Embedder
    from openai import AsyncOpenAI

    db_url = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")
    conn = None
    try:
        conn = await asyncpg.connect(db_url, timeout=5.0)
        rows = await conn.fetch(
            "SELECT id, title, abstract FROM papers WHERE id = ANY($1::text[])",
            [paper_id_a, paper_id_b],
        )
    except Exception as e:
        return f"Database error: {e}"
    finally:
        if conn is not None:
            await conn.close()

    if len(rows) < 2:
        found = {r["id"] for r in rows}
        missing = {paper_id_a, paper_id_b} - found
        return f"Paper(s) not found: {', '.join(missing)}"

    paper_map = {r["id"]: dict(r) for r in rows}
    paper_a = paper_map[paper_id_a]
    paper_b = paper_map[paper_id_b]

    embedder = Embedder()
    vectors = await embedder.embed_batch([paper_a["abstract"], paper_b["abstract"]])
    vec_a = np.array(vectors[0])
    vec_b = np.array(vectors[1])
    similarity = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))

    client = AsyncOpenAI()
    diff_prompt = (
        f"Paper A — {paper_a['title']}:\n{paper_a['abstract']}\n\n"
        f"Paper B — {paper_b['title']}:\n{paper_b['abstract']}\n\n"
        "Summarise the key technical differences between these two papers in 3-5 bullet points."
    )
    completion = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": diff_prompt}],
    )
    summary = completion.choices[0].message.content or ""

    return (
        f"Cosine similarity: {similarity:.3f}\n\n"
        f"Paper A: {paper_a['title']} ({paper_id_a})\n"
        f"Paper B: {paper_b['title']} ({paper_id_b})\n\n"
        f"Key differences:\n{summary}"
    )


@tool
async def arxiv_live_search(query: str, max_results: int = 5) -> str:
    """
    Search the live ArXiv API for recent papers not yet in the local index.

    Args:
        query: Search terms
        max_results: Number of results to return (max 10)

    Returns:
        Formatted list of paper titles, IDs, and abstracts.
    """
    import arxiv

    max_results = min(max_results, 10)
    try:
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        results = list(search.results())
    except Exception as e:
        return f"ArXiv API error: {e}"

    if not results:
        return "No results found on ArXiv."

    lines: list[str] = []
    for r in results:
        paper_id = r.entry_id.split("/")[-1]
        authors = ", ".join(a.name for a in r.authors[:3])
        if len(r.authors) > 3:
            authors += f" et al. ({len(r.authors)} total)"
        lines.append(f"[{paper_id}] {r.title}")
        lines.append(f"Authors: {authors} | Published: {r.published.strftime('%Y-%m-%d')}")
        lines.append(r.summary[:300] + ("..." if len(r.summary) > 300 else ""))
        lines.append("")
    return "\n".join(lines)


@tool
async def citation_formatter(claims: list[dict]) -> str:
    """
    Format a list of claims + paper IDs into structured citation output.
    Uses GPT-4o-mini with a citation formatting prompt.

    Args:
        claims: [{"claim": "...", "paper_id": "..."}]

    Returns:
        Structured JSON citation block.
    """
    from openai import AsyncOpenAI

    if not claims:
        return json.dumps({"citations": []})

    client = AsyncOpenAI()
    claims_text = "\n".join(
        f"{i + 1}. Claim: {c.get('claim', '')} (Paper ID: {c.get('paper_id', 'unknown')})"
        for i, c in enumerate(claims)
    )
    prompt = (
        "Format the following research claims into a structured citation block.\n"
        "Return valid JSON with key 'citations' containing a list of objects, each with:\n"
        "  - 'claim': the claim text\n"
        "  - 'paper_id': the ArXiv paper ID\n"
        "  - 'citation_text': a formatted academic citation string\n\n"
        f"Claims:\n{claims_text}\n\n"
        "Return ONLY valid JSON."
    )

    completion = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return completion.choices[0].message.content or json.dumps({"citations": []})


# All tools exported for agent registration
ALL_TOOLS = [
    rag_search,
    paper_metadata,
    semantic_compare,
    arxiv_live_search,
    citation_formatter,
]
