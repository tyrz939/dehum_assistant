#!/usr/bin/env python3
"""
batch_test.py  – fire a list of prompts at your dehumidifier assistant
and log the results to YYYY-MM-DD_HHMM_testlog.txt
"""

import sys, time, datetime, requests

# ----------------------------------------------------------------------
API_URL = "http://localhost:5001/api/assistant"   # adjust if different
TIMEOUT = 60                                       # seconds per request
HEADERS = {"Content-Type": "application/json"}
# ----------------------------------------------------------------------

def run_one(prompt: str) -> str:
    """Send a single prompt; return full streamed text reply."""
    resp = requests.post(API_URL,
                         json={"input": prompt},
                         headers=HEADERS,
                         stream=True,
                         timeout=TIMEOUT)
    resp.raise_for_status()

    chunks = []
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        chunks.append(chunk)
    return "".join(chunks).strip()

def main(prompt_file: str):
    # read prompts
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompts = [line.strip() for line in f if line.strip()]

    # open log file
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    logname = f"{stamp}_testlog.txt"
    with open(logname, "w", encoding="utf-8") as log:
        for i, p in enumerate(prompts, 1):
            print(f"[{i}/{len(prompts)}] {p[:60]}...", flush=True)
            try:
                answer = run_one(p)
            except Exception as e:
                answer = f"ERROR: {e}"
            # neat, readable block
            log.write(f"Q{i}: {p}\n")
            log.write(f"A{i}: {answer}\n")
            log.write("-" * 60 + "\n")
            log.flush()       # safety on crashes

    print(f"\nDone. Results saved to {logname}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python batch_test.py prompts.txt")
    main(sys.argv[1])
