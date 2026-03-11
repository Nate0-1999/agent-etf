from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Agentic Indexing stack.")
    parser.add_argument("profile", choices=["manual", "verification", "debug"])
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=3000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--python-bin", default=os.getenv("PYTHON_BIN", ".venv/bin/python"))
    parser.add_argument("--node-bin", default=os.getenv("NODE_BIN", "npm"))
    return parser.parse_args()


def prefixed_stream(process: subprocess.Popen[str], prefix: str) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{prefix}] {line.rstrip()}", flush=True)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    runtime_build_id = f"{args.profile}-{int(time.time())}"
    shared_env = os.environ.copy()
    shared_env.update(
        {
            "AGENTIC_PROFILE": args.profile,
            "AGENTIC_RUNTIME_BUILD_ID": runtime_build_id,
            "AGENTIC_JSON_LOGS": "1",
            "AGENTIC_ENV": "development",
        }
    )

    api_env = shared_env.copy()
    web_env = shared_env.copy()
    web_env["AGENTIC_API_ORIGIN"] = f"http://{args.host}:{args.api_port}"

    if args.profile == "verification":
        api_env.update(
            {
                "AGENTIC_TEST_MODE": "1",
                "DATABASE_URL": "",
                "OPENROUTER_API_KEY": "",
                "EXA_API_KEY": "",
                "APPROVAL_STEP3_COOLDOWN_SECONDS": "0",
            }
        )

    print(
        json.dumps(
            {
                "type": "stack_startup",
                "profile": args.profile,
                "runtime_build_id": runtime_build_id,
                "api_origin": web_env["AGENTIC_API_ORIGIN"],
                "api_port": args.api_port,
                "web_port": args.web_port,
            }
        ),
        flush=True,
    )

    api_command = [
        args.python_bin,
        "-m",
        "uvicorn",
        "apps.api.agent_etf_api.main:app",
        "--host",
        args.host,
        "--port",
        str(args.api_port),
    ]
    if args.profile != "verification":
        api_command.append("--reload")

    web_command = [
        args.node_bin,
        "run",
        "dev",
        "--",
        "--hostname",
        args.host,
        "--port",
        str(args.web_port),
    ]

    api_process = subprocess.Popen(
        api_command,
        cwd=root,
        env=api_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    web_process = subprocess.Popen(
        web_command,
        cwd=root / "apps" / "web",
        env=web_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    threads = [
        threading.Thread(target=prefixed_stream, args=(api_process, "api"), daemon=True),
        threading.Thread(target=prefixed_stream, args=(web_process, "web"), daemon=True),
    ]
    for thread in threads:
        thread.start()

    def terminate(*_: object) -> None:
        for process in (api_process, web_process):
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    try:
        while True:
            api_return = api_process.poll()
            web_return = web_process.poll()
            if api_return is not None or web_return is not None:
                return api_return or web_return or 0
            time.sleep(0.1)
    finally:
        terminate()


if __name__ == "__main__":
    raise SystemExit(main())
