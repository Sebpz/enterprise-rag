"""
Module 4 — Guardrails Pipeline
Dual-layer safety system: input checks before LLM, output checks after.

Every decision is logged to Postgres with reason codes for audit + analytics.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Decision(str, Enum):
    PASS  = "PASS"
    BLOCK = "BLOCK"
    WARN  = "WARN"


class ReasonCode(str, Enum):
    CLEAN          = "CLEAN"
    OFF_TOPIC      = "OFF_TOPIC"
    PII_DETECTED   = "PII_DETECTED"
    INJECTION      = "PROMPT_INJECTION"
    UNFAITHFUL     = "UNFAITHFUL_OUTPUT"
    TOXIC          = "TOXIC_OUTPUT"
    BUDGET_EXCEEDED = "AGENT_BUDGET_EXCEEDED"
    LOOP_DETECTED  = "AGENT_LOOP_DETECTED"


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
    Fail-fast: if any check returns BLOCK, the pipeline stops.

    Usage:
        pipeline = GuardrailPipeline()

        # Before LLM call
        result = await pipeline.check_input(query, trace_id)
        if not result.passed:
            return blocked_response(result)

        # After LLM call
        result = await pipeline.check_output(response, retrieved_chunks, trace_id)
    """

    async def check_input(self, query: str, trace_id: str) -> PipelineResult:
        """
        Run all input guardrails in parallel.
        Returns immediately on first BLOCK.
        """
        start = time.perf_counter()

        # TODO: run these concurrently with asyncio.gather
        # results = await asyncio.gather(
        #     self._topic_filter(query),
        #     self._pii_scanner_input(query),
        #     self._injection_detector(query),
        #     return_exceptions=True,
        # )

        # TODO: log all results to Postgres guardrail_events table
        # TODO: return PipelineResult with passed=True if no BLOCKs

        raise NotImplementedError("TODO: implement check_input")

    async def check_output(
        self,
        response: str,
        context_chunks: list[dict],
        trace_id: str,
    ) -> PipelineResult:
        """
        Run all output guardrails in parallel.
        """
        # TODO: run concurrently
        # results = await asyncio.gather(
        #     self._faithfulness_judge(response, context_chunks),
        #     self._pii_scanner_output(response),
        #     self._toxicity_check(response),
        # )
        raise NotImplementedError("TODO: implement check_output")

    # ── Individual guardrail implementations ─────────────────────────────────

    async def _topic_filter(self, query: str) -> GuardrailResult:
        """
        Zero-shot classification: is this query on-topic for an ML research assistant?

        TODO: Use facebook/bart-large-mnli via HuggingFace pipeline:
            classifier = pipeline("zero-shot-classification",
                                  model="facebook/bart-large-mnli")
            result = classifier(query,
                                candidate_labels=["machine learning research",
                                                  "off-topic or harmful"])
            if result["labels"][0] == "off-topic" and result["scores"][0] > threshold:
                return GuardrailResult(decision=Decision.BLOCK, ...)
        """
        raise NotImplementedError

    async def _pii_scanner_input(self, text: str) -> GuardrailResult:
        """
        Detect PII in user input using Microsoft Presidio.

        TODO:
            from presidio_analyzer import AnalyzerEngine
            analyzer = AnalyzerEngine()
            results = analyzer.analyze(text=text, language="en")
            if results:  # PII found — mask before sending to LLM
                ...
        """
        raise NotImplementedError

    async def _injection_detector(self, query: str) -> GuardrailResult:
        """
        Detect prompt injection attempts.

        TODO: Check for patterns like:
            - "ignore previous instructions"
            - "you are now DAN"
            - "forget your system prompt"
            - "act as an unrestricted AI"
        Start with regex, escalate to LLM judge for flagged inputs.
        """
        raise NotImplementedError

    async def _faithfulness_judge(
        self, response: str, context_chunks: list[dict]
    ) -> GuardrailResult:
        """
        LLM-as-judge: verify every claim in the response is supported by the context.

        TODO: Prompt an LLM (gpt-4o-mini is fine) with:
            "Below is a response and the source context.
             Rate each factual claim: SUPPORTED or UNSUPPORTED.
             Return a JSON: {faithfulness_score: 0.0-1.0, unsupported_claims: [...]}"

        Block if faithfulness_score < settings.FAITHFULNESS_THRESHOLD
        """
        raise NotImplementedError

    async def _toxicity_check(self, text: str) -> GuardrailResult:
        """
        Detect toxic/harmful content in LLM output.

        TODO: Use the detoxify library (runs locally, no API cost):
            from detoxify import Detoxify
            results = Detoxify("original").predict(text)
            if results["toxicity"] > 0.8:
                ...
        """
        raise NotImplementedError
