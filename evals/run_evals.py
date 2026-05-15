"""
Module 5 — Evaluation Framework
RAGAs-based eval suite with golden dataset and regression gate.

Run before merging any prompt or config change:
    python -m evals.run_evals --config v2
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"


@dataclass
class EvalConfig:
    prompt_version: str = "v2"
    model: str = "gpt-4o-mini"
    top_k: int = 5
    regression_threshold: float = 0.05   # fail if any metric drops more than 5%


@dataclass
class EvalReport:
    config_version: str
    faithfulness: float
    answer_relevance: float
    context_precision: float
    context_recall: float
    questions_tested: int
    passed_regression: bool
    timestamp: str = datetime.utcnow().isoformat()

    def print_summary(self):
        try:
            status = "✅ PASSED" if self.passed_regression else "❌ FAILED"
        except UnicodeEncodeError:
            status = "[PASSED]" if self.passed_regression else "[FAILED]"
        print(f"\n{status} — Eval Report ({self.config_version})")
        print(f"  Faithfulness:       {self.faithfulness:.3f}")
        print(f"  Answer Relevance:   {self.answer_relevance:.3f}")
        print(f"  Context Precision:  {self.context_precision:.3f}")
        print(f"  Context Recall:     {self.context_recall:.3f}")
        print(f"  Questions tested:   {self.questions_tested}")


def load_golden_dataset() -> list[dict]:
    """
    Load the golden dataset from JSON.

    Each entry shape:
    {
        "question":     "What optimiser does the original Transformer use?",
        "ground_truth": "The Transformer uses the Adam optimiser.",
        "paper_id":     "1706.03762",
        "difficulty":   "easy",
        "expected_know": true
    }
    """
    if not GOLDEN_DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Golden dataset not found at {GOLDEN_DATASET_PATH}. "
            "See evals/README.md for instructions on building it."
        )
    with open(GOLDEN_DATASET_PATH) as f:
        return json.load(f)


async def run_eval_suite(config: EvalConfig) -> EvalReport:
    """
    Run the full evaluation suite against the golden dataset.
    Raises EvalRegressionError if any metric drops beyond regression_threshold vs. last run.
    """
    import os
    import asyncpg
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    except ImportError as exc:
        raise ImportError(
            "RAGAs and datasets are required for evaluation. "
            "Install with: pip install ragas datasets"
        ) from exc
    from rag.pipeline import RAGPipeline

    # 1. Load golden dataset — filter to questions the system is expected to know
    golden = [
        item for item in load_golden_dataset()
        if item.get("expected_know", True) and item.get("ground_truth", "").strip()
    ]
    logger.info("Loaded %d evaluatable golden questions (expected_know=True with ground_truth)", len(golden))

    # 2. Run RAG pipeline for each question
    rag = RAGPipeline()
    results = []  # (question, answer, chunks, ground_truth)

    for item in golden:
        try:
            rag_response = await rag.query(item["question"])
            results.append((
                item["question"],
                rag_response.answer,
                rag_response.chunks_used,
                item["ground_truth"],
            ))
        except Exception as e:
            logger.warning("Failed to run RAG for question %r: %s", item["question"][:50], e)

    if not results:
        raise RuntimeError("No successful RAG evaluations — check RAG pipeline and golden dataset")

    # 3. Build RAGAs Dataset
    ragas_dataset = Dataset.from_list([
        {
            "question": q,
            "answer": a,
            "contexts": [c.text for c in chunks],
            "ground_truth": gt,
        }
        for q, a, chunks, gt in results
    ])

    # 4. Run RAGAs evaluation
    logger.info("Running RAGAs evaluation on %d questions…", len(results))
    scores = evaluate(
        ragas_dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    faithfulness_score = float(scores["faithfulness"])
    answer_relevance_score = float(scores["answer_relevancy"])
    context_precision_score = float(scores["context_precision"])
    context_recall_score = float(scores["context_recall"])

    # 5-7. Load previous run, check regression, save new run
    db_url = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")
    passed_regression = True

    try:
        conn = await asyncpg.connect(db_url, timeout=5.0)
        try:
            # 5. Load last eval for regression comparison
            prev = await conn.fetchrow(
                "SELECT faithfulness, answer_relevance, context_precision, context_recall "
                "FROM eval_runs WHERE passed_regression = TRUE ORDER BY created_at DESC LIMIT 1"
            )

            # 6. Regression gate
            if prev is not None:
                regressions = []
                metric_pairs = [
                    ("faithfulness",       faithfulness_score,       float(prev["faithfulness"] or 0)),
                    ("answer_relevance",   answer_relevance_score,   float(prev["answer_relevance"] or 0)),
                    ("context_precision",  context_precision_score,  float(prev["context_precision"] or 0)),
                    ("context_recall",     context_recall_score,     float(prev["context_recall"] or 0)),
                ]
                for name, current, previous in metric_pairs:
                    drop = previous - current
                    if drop > config.regression_threshold:
                        regressions.append(
                            f"{name}: {previous:.3f} → {current:.3f} (drop={drop:.3f})"
                        )
                if regressions:
                    passed_regression = False
                    logger.warning("Regression detected: %s", "; ".join(regressions))

            # 7. Save results to Postgres
            await conn.execute(
                "INSERT INTO eval_runs"
                "(config_version,faithfulness,answer_relevance,context_precision,"
                "context_recall,questions_tested,passed_regression) VALUES($1,$2,$3,$4,$5,$6,$7)",
                config.prompt_version,
                faithfulness_score,
                answer_relevance_score,
                context_precision_score,
                context_recall_score,
                len(results),
                passed_regression,
            )
        finally:
            await conn.close()
    except Exception as e:
        logger.error("Database operation failed during eval: %s", e)

    report = EvalReport(
        config_version=config.prompt_version,
        faithfulness=faithfulness_score,
        answer_relevance=answer_relevance_score,
        context_precision=context_precision_score,
        context_recall=context_recall_score,
        questions_tested=len(results),
        passed_regression=passed_regression,
    )

    if not passed_regression:
        raise EvalRegressionError(
            f"Eval regression detected for config {config.prompt_version}. "
            "Check logs for details."
        )

    return report


class EvalRegressionError(Exception):
    """Raised when an eval metric regresses beyond the allowed threshold."""
    pass


async def _create_golden_dataset(questions: list[str]) -> None:
    """Run RAG on seed questions and save results as a starter golden dataset."""
    from rag.pipeline import RAGPipeline
    rag = RAGPipeline()
    entries = []
    for q in questions:
        try:
            resp = await rag.query(q)
            entries.append({
                "question": q,
                "ground_truth": "",
                "paper_id": resp.citations[0]["paper_id"] if resp.citations else "",
                "difficulty": "medium",
                "expected_know": True,
            })
            logger.info("Ran RAG for: %s", q[:60])
        except Exception as e:
            logger.warning("Failed for %r: %s", q[:50], e)
    with open(GOLDEN_DATASET_PATH, "w") as f:
        import json as _json
        _json.dump(entries, f, indent=2)
    print(f"Saved {len(entries)} questions to {GOLDEN_DATASET_PATH}")
    print("Edit 'ground_truth' fields manually before using this dataset for evaluation.")


if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(description="Run RAGAs eval suite")
    parser.add_argument("--config", default="v2", help="Prompt version to evaluate")
    parser.add_argument("--no-regression-gate", action="store_true")
    parser.add_argument(
        "--create-golden",
        nargs="+",
        metavar="QUESTION",
        help="Run RAG on these questions and save as starter golden dataset",
    )
    args = parser.parse_args()

    if args.create_golden:
        asyncio.run(_create_golden_dataset(args.create_golden))
        sys.exit(0)

    cfg = EvalConfig(prompt_version=args.config)
    try:
        report = asyncio.run(run_eval_suite(cfg))
        report.print_summary()
    except EvalRegressionError as e:
        if args.no_regression_gate:
            print(f"WARNING: {e}")
        else:
            print(f"ERROR: {e}")
            sys.exit(1)
