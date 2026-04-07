"""PCI-safe DTMF digit collector.

Card numbers are captured server-side via SIP DTMF events and NEVER
forwarded to the LLM context.  The agent speaks TTS prompts directly
while the collector silently accumulates keypad digits.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from livekit import rtc

logger = logging.getLogger("elite-agent.dtmf")

TERMINATOR = "#"
PER_DIGIT_TIMEOUT = 8.0  # seconds to wait for the next keypress


@dataclass
class DTMFResult:
    digits: str = ""
    timed_out: bool = False
    terminated: bool = False


class DTMFCollector:
    """Listens for ``rtc.SipDTMF`` events and collects digits.

    Usage::

        collector = DTMFCollector(room)
        result = await collector.collect(expected_digits=16)
        card_number = result.digits
    """

    def __init__(self, room: rtc.Room):
        self._room = room
        self._digits: list[str] = []
        self._done = asyncio.Event()
        self._expected = 0

    async def collect(
        self,
        expected_digits: int = 0,
        timeout_per_digit: float = PER_DIGIT_TIMEOUT,
    ) -> DTMFResult:
        self._digits.clear()
        self._done.clear()
        self._expected = expected_digits

        def _on_dtmf(dtmf_event: rtc.SipDTMF):
            digit = dtmf_event.digit
            logger.debug("DTMF digit received: %s", "*" if self._expected >= 12 else digit)
            if digit == TERMINATOR:
                self._done.set()
                return
            self._digits.append(digit)
            if self._expected and len(self._digits) >= self._expected:
                self._done.set()

        self._room.on("sip_dtmf_received", _on_dtmf)

        timed_out = False
        try:
            # Total timeout = per-digit × (expected or generous default)
            total = timeout_per_digit * (expected_digits or 20)
            await asyncio.wait_for(self._done.wait(), timeout=total)
        except asyncio.TimeoutError:
            timed_out = True
        finally:
            # Best-effort listener cleanup
            try:
                self._room.off("sip_dtmf_received", _on_dtmf)
            except Exception:
                pass

        result = DTMFResult(
            digits="".join(self._digits),
            timed_out=timed_out,
            terminated=not timed_out,
        )
        logger.info(
            "DTMF collect done  digits_len=%d timed_out=%s",
            len(result.digits),
            result.timed_out,
        )
        return result
