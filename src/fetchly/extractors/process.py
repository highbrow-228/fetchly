import asyncio
import contextlib
import os
import signal

from pydantic import BaseModel, Field

from fetchly.extractors.base import ExtractionTimeoutError


class ProcessOutput(BaseModel, frozen=True):
    returncode: int = Field(description="Exit code of the process; negative = killed by a signal")
    stdout: str = Field(description="What the process printed to stdout")
    stderr: str = Field(description="What the process printed to stderr")

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
        returncode=process.returncode or 0,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
    )
