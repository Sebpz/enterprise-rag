"""
Module 7 — Agent Tools
Functions decorated with @tool that agents can call.
Each tool is a plain async Python function — keep them focused and testable.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# TODO: from langchain_core.tools import tool


# @tool
async def rag_search(query: str, category: str | None = None, year: int | None = None) -> str:
    """
    Search the ArXiv knowledge base for relevant papers.

    Args:
        query: Natural language search query
        category: Optional ArXiv category filter (e.g. 'cs.AI', 'cs.LG')
        year: Optional year filter

    Returns:
        Formatted string of relevant chunks with paper IDs and titles.

    TODO: call RAGPipeline().query() and format the chunks as a readable string
    """
    raise NotImplementedError("TODO: implement rag_search tool")


# @tool
async def paper_metadata(paper_id: str) -> str:
    """
    Fetch structured metadata for a specific ArXiv paper.

    Args:
        paper_id: ArXiv paper ID (e.g. '1706.03762')

    Returns:
        JSON string with title, authors, abstract, date, category.

    TODO: SELECT * FROM papers WHERE id = paper_id
    """
    raise NotImplementedError("TODO: implement paper_metadata tool")


# @tool
async def semantic_compare(paper_id_a: str, paper_id_b: str) -> str:
    """
    Compare two ArXiv papers by embedding their abstracts and computing similarity.

    Returns:
        Similarity score + a brief summary of key differences.

    TODO:
    1. Fetch abstracts for both papers from Postgres
    2. Embed both with the same model used in ingestion
    3. Compute cosine similarity
    4. Prompt LLM with both abstracts: "Summarise the key technical differences"
    """
    raise NotImplementedError("TODO: implement semantic_compare tool")


# @tool
async def arxiv_live_search(query: str, max_results: int = 5) -> str:
    """
    Search the live ArXiv API for recent papers not yet in the local index.

    Args:
        query: Search terms
        max_results: Number of results to return (max 10)

    Returns:
        Formatted list of paper titles, IDs, and abstracts.

    TODO: use the arxiv Python library:
        import arxiv
        search = arxiv.Search(query=query, max_results=max_results,
                              sort_by=arxiv.SortCriterion.SubmittedDate)
        results = list(search.results())
    """
    raise NotImplementedError("TODO: implement arxiv_live_search tool")


# @tool
async def citation_formatter(claims: list[dict]) -> str:
    """
    Format a list of claims + paper IDs into structured citation output.
    Uses the fine-tuned Mistral model (Module 9) when available.

    Args:
        claims: [{"claim": "...", "paper_id": "..."}]

    Returns:
        Structured JSON citation block.

    TODO: if settings.USE_FINETUNED_CITATIONS, route to Ollama fine-tuned model
          else fall back to GPT-4o-mini with citation formatting prompt
    """
    raise NotImplementedError("TODO: implement citation_formatter tool")


# All tools exported for agent registration
ALL_TOOLS = [
    rag_search,
    paper_metadata,
    semantic_compare,
    arxiv_live_search,
    citation_formatter,
]
