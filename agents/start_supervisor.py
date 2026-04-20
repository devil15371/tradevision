#!/usr/bin/env python3
"""
TradeVision — Start Supervisor Server
======================================
Launches a vLLM OpenAI-compatible server for Qwen3-30B-A3B.
Run this BEFORE starting the FastAPI server to enable HMAS mode.

Usage:
    python agents/start_supervisor.py

The server will be available at: http://localhost:8001/v1
"""
import os
import sys
import subprocess

MODEL = os.getenv("SUPERVISOR_MODEL", "Qwen/Qwen3-30B-A3B")
PORT  = int(os.getenv("SUPERVISOR_PORT", "8001"))
GPU_MEMORY_UTIL = float(os.getenv("SUPERVISOR_GPU_UTIL", "0.45"))

print(f"""
╔══════════════════════════════════════════════════════════╗
║        TradeVision Supervisor Server                     ║
║  Model : {MODEL:<40}  ║
║  Port  : {PORT:<40}  ║
║  GPU   : {GPU_MEMORY_UTIL*100:.0f}% utilisation budget                     ║
╚══════════════════════════════════════════════════════════╝

Starting vLLM...
(The server will be ready when you see "INFO: Application startup complete")
""")

cmd = [
    sys.executable, "-m", "vllm.entrypoints.openai.api_server",
    "--model", MODEL,
    "--port", str(PORT),
    "--host", "0.0.0.0",
    "--gpu-memory-utilization", str(GPU_MEMORY_UTIL),
    "--max-model-len", "8192",
    "--dtype", "bfloat16",
    "--quantization", "bitsandbytes",
    "--load-format", "bitsandbytes",
    "--trust-remote-code",
    "--enable-prefix-caching",
    "--served-model-name", "Qwen/Qwen3-30B-A3B",
]

try:
    subprocess.run(cmd, check=True)
except KeyboardInterrupt:
    print("\n[Supervisor] Stopped.")
except subprocess.CalledProcessError as e:
    print(f"\n[Supervisor] Error: {e}")
    sys.exit(1)
