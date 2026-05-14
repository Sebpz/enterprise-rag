"""
Module 9 — Training Data Generator
Uses GPT-4o to generate synthetic (instruction, input, output) training examples
for citation formatting fine-tuning.

Run: python fine_tuning/generate_training_data.py --n 800 --output fine_tuning/data/
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Prompt for generating training examples ───────────────────────────────────
GENERATOR_SYSTEM_PROMPT = """You are generating training data for a citation-formatting model.

For each request, produce a valid JSON training example with this exact schema:
{
    "instruction": "Answer the question using only the context. Format response as JSON with: answer (str), citations (list of {paper_id, claim, quote_fragment}), confidence (0-1 float).",
    "input": "Question: <question>\n\nContext:\n[<paper_id>] <title>\n<abstract_excerpt>",
    "output": {
        "answer": "<concise answer>",
        "citations": [
            {
                "paper_id": "<arxiv_id>",
                "claim": "<the specific claim being cited>",
                "quote_fragment": "<exact short phrase from context, under 15 words>"
            }
        ],
        "confidence": <0.0 to 1.0>
    }
}

Rules:
- output.answer must only use information from the context
- Every factual sentence in output.answer must have a citation
- quote_fragment must be a verbatim snippet from the context
- confidence should reflect how completely the context answers the question
- Vary question types: factual, comparative, methodological, definitional
"""

# ── Sample ArXiv paper stubs for data generation ─────────────────────────────
SAMPLE_PAPERS = [
    {
        "id": "1706.03762",
        "title": "Attention Is All You Need",
        "excerpt": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms. The model achieves 28.4 BLEU on WMT 2014 English-to-German translation. We used the Adam optimizer with beta1=0.9, beta2=0.98 and epsilon=10^-9.",
    },
    {
        "id": "1810.04805",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "excerpt": "BERT is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context. BERT obtains new state-of-the-art results on eleven natural language processing tasks.",
    },
    {
        "id": "2005.14165",
        "title": "Language Models are Few-Shot Learners",
        "excerpt": "GPT-3 has 175 billion parameters and can perform tasks with few or no examples. We train on 300 billion tokens of text. The model shows strong performance on translation, question-answering and cloze tasks.",
    },
]


def generate_training_examples(n: int, output_dir: Path) -> None:
    """
    Generate n training examples using GPT-4o and write to JSONL files.

    TODO:
    1. For each example, randomly select 1-3 papers from SAMPLE_PAPERS
       (or better: load from your actual ingested ArXiv data)
    2. Call GPT-4o with GENERATOR_SYSTEM_PROMPT to generate a Q&A pair
    3. Validate the output JSON schema
    4. Write to train.jsonl (90%) and eval.jsonl (10%)

    Example OpenAI call:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate 1 training example using these papers: {papers}"}
            ],
            response_format={"type": "json_object"}  # enforces JSON output
        )
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    eval_path  = output_dir / "eval.jsonl"

    logger.info("Generating %d training examples...", n)

    # TODO: implement generation loop
    # Split 90/10 into train/eval
    # Write each example as a JSON line
    raise NotImplementedError("TODO: implement generate_training_examples")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=800)
    parser.add_argument("--output", type=Path, default=Path("fine_tuning/data"))
    args = parser.parse_args()
    generate_training_examples(args.n, args.output)
