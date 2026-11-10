"""Subprocess runner with a hard timeout."""

import asyncio
import contextlib
import os
import signal
from dataclasses import dataclass

from fetchly.extractors.base import ExtractionTimeoutError


@dataclass(frozen=True, slots=True)
class ProcessOutput:
    returncode: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return (self.stdout + "\n" + self.stderr).lower()


async def run_process(command: list[str], timeout_seconds: float) -> ProcessOutput:
    """Run a command; on timeout or cancellation kill its whole process group."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,  # own group, so children (ffmpeg) die with it
    )
    try:
        async with asyncio.timeout(timeout_seconds):
            stdout, stderr = await process.communicate()
    except TimeoutError as error:
        raise ExtractionTimeoutError(command[0]) from error
    finally:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
    return ProcessOutput(
        process.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    )
