#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
RENDERER = HERE.parent / "render_stock_research_html.py"

def verify(path: Path, signature: bytes | None = None):
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"missing or empty artifact: {path}")
    if signature and path.read_bytes()[:len(signature)] != signature:
        raise RuntimeError(f"invalid artifact signature: {path}")

def main():
    parser = argparse.ArgumentParser(description="Build JSON-adjacent HTML and PDF artifacts")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    data = json.loads(bundle.read_text(encoding="utf-8"))
    html, pdf = bundle.with_suffix(".html"), bundle.with_suffix(".pdf")
    command = [sys.executable, str(RENDERER), str(bundle)]
    if data.get("status") in {"partial", "halted", "dropped"}:
        command.append("--allow-incomplete")
    subprocess.run(command, check=True)
    verify(html)
    playwright = shutil.which("playwright")
    if not playwright:
        raise RuntimeError("playwright CLI not found")
    with tempfile.TemporaryDirectory(prefix="stock-research-pdf-") as temp:
        temporary = Path(temp) / "report.pdf"
        subprocess.run([playwright, "pdf", "--paper-format", "A4", "--wait-for-timeout", "1000", html.as_uri(), str(temporary)], check=True)
        verify(temporary, b"%PDF-")
        shutil.copy2(temporary, pdf)
    verify(pdf, b"%PDF-")
    print(json.dumps({"status":"complete","json":str(bundle),"html":str(html),"pdf":str(pdf)}, indent=2))

if __name__ == "__main__":
    main()
