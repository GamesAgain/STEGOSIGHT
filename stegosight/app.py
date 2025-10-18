"""Entry point for the STEGOSIGHT application."""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from .core.analysis import AnalysisResult, IAnalyzer
from .core.neutralize import INeutralizer
from .core.stego_engine import EmbedOptions, IStegoEngine
from .ui.main_window import MainWindow


@dataclass(slots=True)
class MockStegoEngine(IStegoEngine):
    """Mock implementation returning deterministic responses for the UI."""

    def estimate_capacity(self, carrier: Path) -> int:
        return 1024 * 64

    def embed(self, carrier: Path, payload: bytes, opt: EmbedOptions) -> Path:
        opt.output_dir.mkdir(parents=True, exist_ok=True)
        output = opt.output_dir / f"{opt.output_dir.name}_stego.bin"
        output.write_bytes(payload or b"mock")
        return output

    def extract(self, stego_file: Path, password: str | None) -> bytes:
        return stego_file.read_bytes() if stego_file.exists() else b"mock-payload"


class MockAnalyzer(IAnalyzer):
    """Analyzer producing pseudo-random results for demonstration."""

    def scan(self, file: Path, techniques: list[str] | None = None) -> AnalysisResult:
        random.seed(file.name)
        risk = random.randint(5, 95)
        flags = {"chi_square": random.random(), "histogram": random.random(), "ela": random.random()}
        metadata = {"size": file.stat().st_size if file.exists() else 0}
        return AnalysisResult(risk_score=risk, flags=flags, metadata=metadata)


class MockNeutralizer(INeutralizer):
    """Neutralizer that copies the file to a new location."""

    def neutralize(self, file: Path, tier: str) -> Path:  # type: ignore[override]
        sanitized = file.with_suffix(f".neutralized.{tier}{file.suffix}")
        if file.exists():
            sanitized.write_bytes(file.read_bytes())
        else:
            sanitized.write_text("neutralized", encoding="utf-8")
        return sanitized


def _run_cli(analyzer: IAnalyzer, paths: Iterable[Path]) -> int:
    for path in paths:
        result = analyzer.scan(path)
        print(f"{path}: risk={result.risk_score} flags={result.flags}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STEGOSIGHT Application")
    parser.add_argument("paths", nargs="*", type=Path, help="Files to scan when using CLI mode")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    args = parser.parse_args(argv)

    analyzer = MockAnalyzer()
    if args.cli:
        return _run_cli(analyzer, args.paths)

    app = QApplication(sys.argv)
    settings_factory = lambda: QSettings("stegosight", "desktop")
    window = MainWindow.create_with_interfaces(MockStegoEngine(), analyzer, MockNeutralizer(), settings_factory)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
