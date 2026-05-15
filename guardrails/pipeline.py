"""
Module 4 — Guardrails Pipeline
Dual-layer safety system: input checks before LLM, output checks after.

Every decision is logged to Postgres with reason codes for audit + analytics.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Decision(str, Enum):
    PASS  = "PASS"
    BLOCK = "BLOCK"
    WARN  = "WARN"


class ReasonCode(str, Enum):
    CLEAN           = "CLEAN"
    OFF_TOPIC       = "OFF_TOPIC"
    PII_DETECTED    = "PII_DETECTED"
    INJECTION       = "PROMPT_INJECTION"
    UNFAITHFUL      = "UNFAITHFUL_OUTPUT"
    TOXIC           = "TOXIC_OUTPUT"
    BUDGET_EXCEEDED = "AGENT_BUDGET_EXCEEDED"
    LOOP_DETECTED   = "AGENT_LOOP_DETECTED"


@dataclass
class GuardrailResult:
    guardrail_name: str
    decision: Decision
    reason_code: ReasonCode
    confidence: float
    latency_ms: float
    detail: str = ""


@dataclass
class PipelineResult:
    passed: bool
    results: list[GuardrailResult]
    blocked_by: str | None = None   # name of the guardrail that blocked

    @property
    def total_latency_ms(self) -> float:
        return sum(r.latency_ms for r in self.results)


class GuardrailPipeline:
    """
    Runs all input or output guardrails in parallel.
    Fail-open: exceptions inside individual guardrails become WARN, not BLOCK.

    Usage:
        pipeline = GuardrailPipeline()

        # Before LLM call
        result = await pipeline.check_input(query, trace_id)
        if not result.passed:
            return blocked_response(result)

        # After LLM call
        result = await pipeline.check_output(response, retrieved_chunks, trace_id)
    """

    def __init__(self) -> None:
        self._topic_model = None
        self._toxicity_model = None
        self._analyzer = None
        self._anonymizer = None
        self._db_url = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")

    async def check_input(self, query: str, trace_id: str) -> PipelineResult:
        """Run all input guardrails in parallel. Returns immediately on first BLOCK."""
        raw = await asyncio.gather(
            self._topic_filter(query),
            self._pii_scanner_input(query),
            self._injection_detector(query),
            return_exceptions=True,
        )
        guardrail_results: list[GuardrailResult] = []
        blocked_by: str | None = None
        for r in raw:
            if isinstance(r, Exception):
                gr = GuardrailResult("error", Decision.WARN, ReasonCode.CLEAN, 0.0, 0.0, str(r))
            else:
                gr = r
            guardrail_results.append(gr)
            if gr.decision == Decision.BLOCK and blocked_by is None:
                blocked_by = gr.guardrail_name

        await self._log_results(guardrail_results, trace_id, "input")
        return PipelineResult(passed=blocked_by is None, results=guardrail_results, blocked_by=blocked_by)

    async def check_output(
        self,
        response: str,
        context_chunks: list[dict],
        trace_id: str,
    ) -> PipelineResult:
        """Run all output guardrails in parallel."""
        raw = await asyncio.gather(
            self._faithfulness_judge(response, context_chunks),
            self._pii_scanner_output(response),
            self._toxicity_check(response),
            return_exceptions=True,
        )
        guardrail_results: list[GuardrailResult] = []
        blocked_by: str | None = None
        for r in raw:
            if isinstance(r, Exception):
                gr = GuardrailResult("error", Decision.WARN, ReasonCode.CLEAN, 0.0, 0.0, str(r))
            else:
                gr = r
            guardrail_results.append(gr)
            if gr.decision == Decision.BLOCK and blocked_by is None:
                blocked_by = gr.guardrail_name

        await self._log_results(guardrail_results, trace_id, "output")
        return PipelineResult(passed=blocked_by is None, results=guardrail_results, blocked_by=blocked_by)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _log_results(
        self, results: list[GuardrailResult], trace_id: str, stage: str
    ) -> None:
        try:
            import asyncpg
            conn = await asyncpg.connect(self._db_url, timeout=2.0)
            try:
                await conn.executemany(
                    "INSERT INTO guardrail_events"
                    "(trace_id,stage,guardrail_name,decision,reason_code,confidence,latency_ms) "
                    "VALUES($1,$2,$3,$4,$5,$6,$7)",
                    [
                        (
                            trace_id, stage, r.guardrail_name,
                            r.decision.value, r.reason_code.value,
                            r.confidence, r.latency_ms,
                        )
                        for r in results
                    ],
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.warning("Failed to log guardrail results: %s", e)

    # ── Individual guardrail implementations ──────────────────────────────────

    async def _topic_filter(self, query: str) -> GuardrailResult:
        """Zero-shot classification: is this on-topic for an ML research assistant?"""
        t0 = time.perf_counter()
        if self._topic_model is None:
            from transformers import pipeline as hf_pipeline
            self._topic_model = hf_pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=int(os.getenv("GUARDRAIL_DEVICE", "-1")),
            )

        result = await asyncio.to_thread(
            self._topic_model,
            query,
            candidate_labels=["machine learning research", "off-topic or harmful request"],
        )
        top_label = result["labels"][0]
        top_score = float(result["scores"][0])
        latency_ms = (time.perf_counter() - t0) * 1000

        if top_label == "off-topic or harmful request" and top_score > 0.75:
            return GuardrailResult(
                "topic_filter", Decision.BLOCK, ReasonCode.OFF_TOPIC, top_score, latency_ms,
                f"Query classified as off-topic (score={top_score:.3f})",
            )
        return GuardrailResult("topic_filter", Decision.PASS, ReasonCode.CLEAN, top_score, latency_ms)

    async def _pii_scanner_input(self, text: str) -> GuardrailResult:
        """Detect + anonymize PII in user input using Microsoft Presidio."""
        t0 = time.perf_counter()
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        if self._analyzer is None:
            self._analyzer = AnalyzerEngine()
        if self._anonymizer is None:
            self._anonymizer = AnonymizerEngine()

        findings = await asyncio.to_thread(self._analyzer.analyze, text=text, language="en")
        latency_ms = (time.perf_counter() - t0) * 1000

        if findings:
            anonymized = await asyncio.to_thread(
                self._anonymizer.anonymize, text=text, analyzer_results=findings
            )
            entity_types = list({r.entity_type for r in findings})
            return GuardrailResult(
                "pii_scanner", Decision.WARN, ReasonCode.PII_DETECTED,
                confidence=1.0, latency_ms=latency_ms,
                detail=f"PII detected: {entity_types}. Anonymized: {anonymized.text}",
            )
        return GuardrailResult("pii_scanner", Decision.PASS, ReasonCode.CLEAN, 0.0, latency_ms)

    async def _pii_scanner_output(self, text: str) -> GuardrailResult:
        """Scan LLM output for accidental PII leakage."""
        return await self._pii_scanner_input(text)

    async def _injection_detector(self, query: str) -> GuardrailResult:
        """Detect prompt injection attempts via regex patterns."""
        import re
        t0 = time.perf_counter()
        patterns = [
            r"ignore (previous|all) instructions",
            r"you are now\b",
            r"forget your (system|previous|instructions)",
            r"act as an? (unrestricted|uncensored|jailbreak)",
            r"disregard (your|all)",
            r"\bDAN\b",
            r"do anything now",
            r"new persona",
            r"pretend (you are|to be) (an? )?(different|unrestricted)",
            r"system\s*prompt",
            r"reveal\s+(your\s+)?(system|instructions|prompt)",
            r"what\s+(are\s+)?your\s+instructions",
        ]
        combined = re.compile("|".join(patterns), re.IGNORECASE)
        match = combined.search(query)
        latency_ms = (time.perf_counter() - t0) * 1000

        if match:
            return GuardrailResult(
                "injection_detector", Decision.BLOCK, ReasonCode.INJECTION,
                1.0, latency_ms, f"Injection pattern detected: '{match.group()}'",
            )
        return GuardrailResult("injection_detector", Decision.PASS, ReasonCode.CLEAN, 0.0, latency_ms)

    async def _faithfulness_judge(
        self, response: str, context_chunks: list[dict]
    ) -> GuardrailResult:
        """LLM-as-judge: verify every claim is supported by the retrieved context."""
        import json
        from openai import AsyncOpenAI
        t0 = time.perf_counter()

        context_text = "\n\n".join(
            f"[Source {i + 1}]: {c.get('text') or c.get('title', '')}"
            for i, c in enumerate(context_chunks[:5])
        )
        prompt = (
            "You are evaluating whether an AI response is faithful to its source context.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Response to evaluate:\n{response}\n\n"
            "Rate the faithfulness. Return ONLY valid JSON:\n"
            '{"faithfulness_score": 0.0-1.0, "unsupported_claims": ["..."]}\n\n'
            "faithfulness_score: 1.0 = fully supported, 0.0 = completely unsupported"
        )

        try:
            client = AsyncOpenAI()
            completion = await client.chat.completions.create(
                model=os.getenv("JUDGE_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            result = json.loads(completion.choices[0].message.content)
            score = float(result.get("faithfulness_score", 1.0))
            latency_ms = (time.perf_counter() - t0) * 1000

            threshold = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.5"))
            if score < threshold:
                return GuardrailResult(
                    "faithfulness_judge", Decision.BLOCK, ReasonCode.UNFAITHFUL,
                    score, latency_ms, f"Faithfulness score {score:.3f} below threshold {threshold}",
                )
            return GuardrailResult("faithfulness_judge", Decision.PASS, ReasonCode.CLEAN, score, latency_ms)
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Faithfulness judge error: %s", e)
            return GuardrailResult("faithfulness_judge", Decision.WARN, ReasonCode.CLEAN, 0.0, latency_ms, str(e))

    async def _toxicity_check(self, text: str) -> GuardrailResult:
        """Detect toxic/harmful content using Detoxify (runs locally)."""
        t0 = time.perf_counter()
        if self._toxicity_model is None:
            try:
                from detoxify import Detoxify
                self._toxicity_model = Detoxify("original")
            except ImportError:
                latency_ms = (time.perf_counter() - t0) * 1000
                return GuardrailResult(
                    "toxicity_check", Decision.WARN, ReasonCode.CLEAN, 0.0, latency_ms,
                    "detoxify not available — skipping toxicity check",
                )

        results = await asyncio.to_thread(self._toxicity_model.predict, text)
        toxicity_score = float(results.get("toxicity", 0.0))
        latency_ms = (time.perf_counter() - t0) * 1000

        if toxicity_score > 0.8:
            return GuardrailResult(
                "toxicity_check", Decision.BLOCK, ReasonCode.TOXIC,
                toxicity_score, latency_ms, f"Toxicity score: {toxicity_score:.3f}",
            )
        return GuardrailResult("toxicity_check", Decision.PASS, ReasonCode.CLEAN, toxicity_score, latency_ms)
