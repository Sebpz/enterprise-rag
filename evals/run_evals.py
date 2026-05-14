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
        status = "✅ PASSED" if self.passed_regression else "❌ FAILED"
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
        "difficulty":   "easy",           // easy / medium / hard / adversarial
        "expected_know": true             // false = "I don't know" expected
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
    Run the full evaluation suite.

    TODO:
    1. Load golden dataset
    2. For each question, run the RAG pipeline to get (answer, contexts)
    3. Build a RAGAs Dataset from (questions, answers, contexts, ground_truths)
    4. Call ragas.evaluate() with the 4 metrics
    5. Load the last eval run from Postgres for regression comparison
    6. Raise EvalRegressionError if any metric drops > regression_threshold
    7. Save results to Postgres eval_runs table
    8. Return EvalReport

    Example RAGAs usage:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from datasets import Dataset

        ragas_dataset = Dataset.from_list([
            {
                "question": q,
                "answer": a,
                "contexts": [c.text for c in chunks],
                "ground_truth": gt,
            }
            for q, a, chunks, gt in results
        ])
        scores = evaluate(ragas_dataset, metrics=[faithfulness, answer_relevancy,
                                                   context_precision, context_recall])
    """
    raise NotImplementedError("TODO: implement run_eval_suite")


class EvalRegressionError(Exception):
    """Raised when an eval metric regresses beyond the allowed threshold."""
    pass


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="v2", help="Prompt version to evaluate")
    parser.add_argument("--no-regression-gate", action="store_true")
    args = parser.parse_args()

    cfg = EvalConfig(prompt_version=args.config)
    report = asyncio.run(run_eval_suite(cfg))
    report.print_summary()
