import asyncio
import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelemetryWriter:

    def __init__(self, path: str):
        self._path = path
        self._lock = asyncio.Lock()
        self._fh = open(self._path, "a", encoding="utf-8")

    async def write(self, record: Dict[str, Any]) -> None:
        record.setdefault("ts", now_iso())
        line = json.dumps(record, ensure_ascii=False)
        async with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()

    async def close(self):
        async with self._lock:
            try:
                self._fh.flush()
            finally:
                self._fh.close()


class SummaryWriter:
    def __init__(self, path: str):
        self._path = path
        self._fh = None

    def open(self):
        exists = os.path.exists(self._path)
        self._fh = open(self._path, "a", encoding="utf-8", newline="")
        if not exists or os.path.getsize(self._path) == 0:
            self._fh.write("concurrency,elapsed_s,success,error\n")
            self._fh.flush()

    def write_row(self, concurrency: int, elapsed_s: float, success: int, error: int):
        if self._fh is None:
            self.open()
        self._fh.write(f"{concurrency},{elapsed_s:.3f},{success},{error}\n")
        self._fh.flush()

    def close(self):
        if self._fh is not None:
            try:
                self._fh.flush()
            finally:
                self._fh.close()
                self._fh = None


def serialize_event(event: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    try:
        ev_type = getattr(event, "type", type(event).__name__)
    except Exception:
        ev_type = type(event).__name__
    payload["type"] = ev_type

    try:
        d = getattr(event, "__dict__", None)
        if isinstance(d, dict) and d:
            def safe_convert(obj: Any) -> Any:
                if isinstance(obj, (str, int, float, bool)) or obj is None:
                    return obj
                if isinstance(obj, dict):
                    return {str(k): safe_convert(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [safe_convert(x) for x in obj]
                return str(obj)

            payload["data"] = safe_convert(d)
            return payload
    except Exception:
        pass

    try:
        payload["raw"] = str(event)
    except Exception:
        payload["raw"] = "<unprintable event>"
    return payload


async def run_session(session_id: int, prompt: str, model: Optional[str], writer: TelemetryWriter) -> bool:
    await writer.write({
        "ts": now_iso(),
        "session_id": session_id,
        "level": "INFO",
        "event": "session_start",
        "model": model or "gpt-realtime",
    })

    client = AsyncAzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    started_at = datetime.now(timezone.utc)
    error: Optional[str] = None
    bytes_received = 0
    tokens_text = 0

    try:
        async with client.realtime.connect(model=model or "gpt-realtime") as connection:
            await writer.write({
                "ts": now_iso(),
                "session_id": session_id,
                "level": "DEBUG",
                "event": "connected",
            })

            await connection.session.update(session={"modalities": ["text"]})  # type: ignore
            await writer.write({
                "ts": now_iso(),
                "session_id": session_id,
                "level": "DEBUG",
                "event": "session_update_sent",
                "modalities": ["text"],
            })

            await connection.conversation.item.create(
                item={
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            )
            await writer.write({
                "ts": now_iso(),
                "session_id": session_id,
                "level": "DEBUG",
                "event": "user_message_sent",
                "prompt": prompt,
            })

            await connection.response.create()
            await writer.write({
                "ts": now_iso(),
                "session_id": session_id,
                "level": "DEBUG",
                "event": "response_create_sent",
            })

            async for evt in connection:
                data = serialize_event(evt)
                data.update({
                    "ts": now_iso(),
                    "session_id": session_id,
                    "level": "TRACE",
                    "event": "rt_event",
                })
                await writer.write(data)

                t = getattr(evt, "type", None)
                if t == "response.text.delta":
                    chunk = getattr(evt, "delta", "")
                    try:
                        tokens_text += len((chunk or "").split())
                    except Exception:
                        pass
                elif t == "response.audio.delta":
                    b64 = getattr(evt, "delta", "")
                    try:
                        import base64
                        bytes_received += len(base64.b64decode(b64))
                    except Exception:
                        pass
                elif t == "response.done":
                    break

    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"
        await writer.write({
            "ts": now_iso(),
            "session_id": session_id,
            "level": "ERROR",
            "event": "session_error",
            "error": error,
        })
    finally:
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        success = error is None
        await writer.write({
            "ts": now_iso(),
            "session_id": session_id,
            "level": "INFO",
            "event": "session_end",
            "duration_ms": duration_ms,
            "bytes_received": bytes_received,
            "text_token_chunks": tokens_text,
            "success": success,
            "error": error,
        })
        return success




def parse_levels(spec: str) -> list[int]:
    levels: list[int] = []
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    for tok in tokens:
        if "-" in tok:
            rng, *step_part = tok.split(":", 1)
            if "-" not in rng:
                raise ValueError(f"Invalid range token: {tok}")
            start_s, end_s = rng.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            step = int(step_part[0]) if step_part else 1
            if step <= 0:
                raise ValueError(f"Step must be > 0 in token: {tok}")
            if end < start:
                raise ValueError(f"End < start in token: {tok}")
            cur = start
            while cur <= end:
                levels.append(cur)
                cur += step
        else:
            levels.append(int(tok))
    return levels


async def run_level(concurrency: int, args: argparse.Namespace, writer: TelemetryWriter) -> tuple[int, int, float]:
    await writer.write({
        "ts": now_iso(),
        "level": "INFO",
        "event": "run_level_start",
        "concurrency": concurrency,
    })
    level_started_at = datetime.now(timezone.utc)
    tasks: list[asyncio.Task] = []
    for i in range(concurrency):
        t = asyncio.create_task(run_session(i + 1, args.prompt, args.model, writer))
        tasks.append(t)
        if args.ramp_interval_ms and i < concurrency - 1:
            await asyncio.sleep(args.ramp_interval_ms / 1000.0)

    completed_flags = await asyncio.gather(*tasks)
    completed = int(sum(1 for ok in completed_flags if ok))
    failed = int(concurrency - completed)
    level_ended_at = datetime.now(timezone.utc)
    elapsed_s = (level_ended_at - level_started_at).total_seconds()

    await writer.write({
        "ts": now_iso(),
        "level": "INFO",
        "event": "run_summary",
        "concurrency": concurrency,
        "sessions": concurrency,
        "completed": completed,
        "failed": failed,
        "duration_ms": int(elapsed_s * 1000),
    })
    await writer.write({
        "ts": now_iso(),
        "level": "INFO",
        "event": "run_level_end",
        "concurrency": concurrency,
    })
    return completed, failed, elapsed_s

async def main_async(args: argparse.Namespace) -> None:
    output = args.output
    if not output:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = f"telemetry-{ts}.jsonl"
    writer = TelemetryWriter(output)

    ts_now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = args.summary or f"summary-{ts_now}.csv"
    summary = SummaryWriter(summary_path)
    summary.open()

    # Determine prompt source (file vs. arg)
    prompt_text = args.prompt
    prompt_source = "arg"
    prompt_file_path = None
    if getattr(args, "prompt_file", None):
        prompt_file_path = args.prompt_file
        try:
            with open(args.prompt_file, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            prompt_source = "file"
        except Exception as ex:
            await writer.write({
                "ts": now_iso(),
                "level": "ERROR",
                "event": "prompt_file_error",
                "error": f"{type(ex).__name__}: {ex}",
                "prompt_file": args.prompt_file,
            })
            prompt_text = args.prompt
            prompt_source = "arg"

    args.prompt = prompt_text

    await writer.write({
        "ts": now_iso(),
        "level": "INFO",
        "event": "run_start",
        "sessions": args.sessions,
        "levels": args.levels,
        "model": args.model or "gpt-realtime",
        "prompt": prompt_text,
        "prompt_source": prompt_source,
        "prompt_file": prompt_file_path,
        "prompt_chars": len(prompt_text) if isinstance(prompt_text, str) else None,
        "pid": os.getpid(),
        "ramp_interval_ms": args.ramp_interval_ms,
    })

    if args.levels:
        levels = parse_levels(args.levels)
        for c in levels:
            completed, failed, elapsed_s = await run_level(c, args, writer)
            summary.write_row(c, elapsed_s, completed, failed)
            print(f"[level {c}] Completed {completed}/{c} in {elapsed_s:.3f}s (failed: {failed})")
    else:
        completed, failed, elapsed_s = await run_level(args.sessions, args, writer)
        summary.write_row(args.sessions, elapsed_s, completed, failed)
        print(f"Completed {completed} of {args.sessions} sessions (failed: {failed}). Elapsed: {elapsed_s:.3f}s")

    await writer.write({
        "ts": now_iso(),
        "level": "INFO",
        "event": "run_end",
    })
    await writer.close()
    summary.close()

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(description="Concurrent RT telemetry driver")
    parser.add_argument(
        "--sessions",
        type=int,
        default=5,
        help="Number of concurrent sessions to run",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="What is the capital of Portugal?",
        help="Prompt to send in each session",
    )
    parser.add_argument(
        "--prompt-file",
        dest="prompt_file",
        type=str,
        default=None,
        help="Path to a file whose entire contents will be used as the prompt",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model/deployment name (defaults to gpt-realtime)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to JSONL telemetry file (default: telemetry-<ts>.jsonl)",
    )
    parser.add_argument(
        "--summary",
        type=str,
        default=None,
        help="Path to summary CSV (default: summary-<ts>.csv)",
    )
    parser.add_argument(
        "--ramp-interval-ms",
        type=int,
        default=0,
        help="Delay between launching each session, to slowly increase concurrency (ms)",
    )
    parser.add_argument(
        "--levels", "-levels",
        type=str,
        default=None,
        help=(
            "Comma-separated concurrency levels, integers or ranges with optional step. "
            "Examples: '1,2,5,10-50:10' -> [1,2,5,10,20,30,40,50]."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
