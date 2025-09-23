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


async def run_connection(conn_id: int, model: Optional[str], hold_s: float, writer: TelemetryWriter) -> bool:
    await writer.write({
        "ts": now_iso(),
        "conn_id": conn_id,
        "level": "INFO",
        "event": "connection_attempt",
        "model": model or "gpt-realtime",
    })

    client = AsyncAzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    started_at = datetime.now(timezone.utc)
    success = False
    closed_reason = None

    try:
        async with client.realtime.connect(model=model or "gpt-realtime") as connection:
            success = True
            await writer.write({
                "ts": now_iso(),
                "conn_id": conn_id,
                "level": "INFO",
                "event": "connection_opened",
            })

            async def listener():
                try:
                    async for evt in connection:
                        data = serialize_event(evt)
                        data.update({
                            "ts": now_iso(),
                            "conn_id": conn_id,
                            "level": "TRACE",
                            "event": "rt_event",
                        })
                        await writer.write(data)
                except Exception as ex:
                    await writer.write({
                        "ts": now_iso(),
                        "conn_id": conn_id,
                        "level": "ERROR",
                        "event": "listener_error",
                        "error": f"{type(ex).__name__}: {ex}",
                    })

            listen_task = asyncio.create_task(listener())

            await asyncio.sleep(max(0.0, hold_s))
            # After hold duration, close the connection
            await writer.write({
                "ts": now_iso(),
                "conn_id": conn_id,
                "level": "INFO",
                "event": "connection_close_initiated",
                "reason": "manual",
            })
            await connection.close()
            closed_reason = "manual"

            # Give listener a chance to flush and finish
            try:
                await asyncio.wait_for(listen_task, timeout=5)
            except asyncio.TimeoutError:
                listen_task.cancel()
                await writer.write({
                    "ts": now_iso(),
                    "conn_id": conn_id,
                    "level": "WARN",
                    "event": "listener_timeout",
                })

    except Exception as ex:
        success = False
        closed_reason = "error"
        await writer.write({
            "ts": now_iso(),
            "conn_id": conn_id,
            "level": "ERROR",
            "event": "connection_error",
            "error": f"{type(ex).__name__}: {ex}",
        })
    finally:
        ended_at = datetime.now(timezone.utc)
        await writer.write({
            "ts": now_iso(),
            "conn_id": conn_id,
            "level": "INFO",
            "event": "connection_closed",
            "success": success,
            "closed_reason": closed_reason,
            "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
        })
        return success


async def main_async(args: argparse.Namespace) -> None:
    output = args.output
    if not output:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = f"telemetry-connections-{ts}.jsonl"
    writer = TelemetryWriter(output)

    await writer.write({
        "ts": now_iso(),
        "level": "INFO",
        "event": "run_start",
        "sessions": args.sessions,
        "model": args.model or "gpt-realtime",
        "pid": os.getpid(),
        "ramp_interval_ms": args.ramp_interval_ms,
        "hold_s": args.hold_s,
    })

    tasks: list[asyncio.Task] = []
    for i in range(args.sessions):
        t = asyncio.create_task(run_connection(i + 1, args.model, args.hold_s, writer))
        tasks.append(t)
        if args.ramp_interval_ms and i < args.sessions - 1:
            await asyncio.sleep(args.ramp_interval_ms / 1000.0)

    successes = 0
    try:
        results = await asyncio.gather(*tasks)
        successes = int(sum(1 for r in results if r))
    finally:
        await writer.write({
            "ts": now_iso(),
            "level": "INFO",
            "event": "run_end",
            "successful_connections": successes,
            "total": args.sessions,
        })
        await writer.close()
        print(f"Successful connections: {successes}/{args.sessions}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realtime connection stress test")
    parser.add_argument(
        "--sessions",
        type=int,
        default=10,
        help="Number of concurrent connections to attempt",
    )
    parser.add_argument(
        "--ramp-interval-ms",
        type=int,
        default=100,
        help="Delay between launching each connection (ms)",
    )
    parser.add_argument(
        "--hold-s",
        type=float,
        default=3.0,
        help="Seconds to hold each connection open before closing",
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
        help="Path to JSONL telemetry file (default: telemetry-connections-<ts>.jsonl)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
