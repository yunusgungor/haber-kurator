"""
Haber Kuratör — LLM Call Module
==================================
Shared async + sync LLM calling for both ScannerMixin and WriterMixin.

Consolidates the repeated `agent.auxiliary_client.async_call_llm` import +
extraction pattern that previously existed in both mixins.
"""

import logging
from typing import Any, List, Dict, Optional

logger = logging.getLogger(__name__)


async def _call_llm_async(
    messages: List[Dict[str, str]],
    task: str = "curator",
) -> Optional[str]:
    """Call the Hermes auxiliary LLM in an async context.

    Args:
        messages: List of dicts with 'role' and 'content'.
        task: Auxiliary task name (default 'curator').

    Returns:
        Extracted text response, or None on failure.
    """
    try:
        from agent.auxiliary_client import async_call_llm
    except ImportError:
        logger.warning("Hermes LLM unavailable outside agent context.")
        return None

    try:
        raw = await async_call_llm(task=task, messages=messages)
        try:
            text = raw.choices[0].message.content
        except (AttributeError, IndexError):
            text = str(raw)

        text = text.strip()
        if text.startswith("```"):
            text = __import__("re").sub(r"^```\w*\n?", "", text)
            text = __import__("re").sub(r"\n```$", "", text)
        return text.strip().strip('"').strip("'").strip('»').strip('«')
    except Exception as exc:
        logger.debug("LLM call failed (%s): %s", type(exc).__name__, str(exc)[:200])
        return None


def call_llm_sync(
    messages: List[Dict[str, str]],
    task: str = "curator",
    timeout: int = 60,
) -> Optional[str]:
    """Synchronous wrapper around _call_llm_async.

    Creates a fresh event loop to avoid asyncio conflicts outside the
    agent runtime (cron, standalone scripts). Designed for WriterMixin.
    """
    import asyncio

    async def do_call() -> Optional[str]:
        return await _call_llm_async(messages, task)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(do_call())
    finally:
        loop.close()


async def call_llm_with_fallback(
    messages: List[Dict[str, str]],
    llm: Any = None,
    task: str = "curator",
) -> Optional[str]:
    """Try an external ``llm.acomplete`` first, then fall back to Hermes.

    This is the primary entry point for ScannerMixin's async methods.
    ``llm`` is an optional Hermes agent LLM handle passed from the agent
    context (e.g. via tool call). When it's available and has ``acomplete``
    we use it directly; otherwise fall back to the Hermes auxiliary client.
    """
    if llm is not None and hasattr(llm, "acomplete"):
        try:
            response = await llm.acomplete(messages)
            text = response.text
            if text:
                return text.strip()
        except Exception as exc:
            logger.debug("llm.acomplete fallback: %s", str(exc)[:200])

    return await _call_llm_async(messages, task)
