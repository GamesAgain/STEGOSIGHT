"""Entry point module for the STEGOSIGHT application."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, Optional

from config import APP_DESCRIPTION, APP_NAME, APP_VERSION
from utils.logger import setup_logger

logger = setup_logger(__name__)


def parse_arguments(argv: Optional[Iterable[str]] = None):
    """Return parsed command line arguments."""

    parser = argparse.ArgumentParser(
        prog="stegosight",
        description=f"{APP_DESCRIPTION} v{APP_VERSION}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} v{APP_VERSION}")

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # ------------------------------------------------------------------
    # Hide command
    # ------------------------------------------------------------------
    hide = subparsers.add_parser(
        "hide",
        help="Hide a payload inside a carrier file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    hide.add_argument("-c", "--carrier", required=True, help="Path to the carrier file")
    payload_group = hide.add_mutually_exclusive_group(required=True)
    payload_group.add_argument("-p", "--payload", help="Path to the payload file")
    payload_group.add_argument("-t", "--text", help="Text to hide inside the carrier")
    hide.add_argument("-o", "--output", help="Path for the resulting stego file")
    hide.add_argument("-m", "--mode", choices=["auto", "manual", "integrated"], default="auto")
    hide.add_argument(
        "--technique",
        "--tech",
        choices=["lsb", "pvd", "dct", "exif", "id3", "append", "audio_lsb", "video_lsb"],
        help="Explicitly select the embedding technique",
    )
    hide.add_argument("--password", "--pw", help="Password for AES-256-GCM encryption")
    hide.add_argument("--openpgp", help="OpenPGP key identifier (reserved for future use)")
    hide.add_argument("--no-analysis", action="store_true", help="Skip risk analysis after embedding")

    # ------------------------------------------------------------------
    # Extract command
    # ------------------------------------------------------------------
    extract = subparsers.add_parser(
        "extract",
        help="Extract a payload from a carrier",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    extract.add_argument("-i", "--input", required=True, help="Path to the suspected stego file")
    extract.add_argument("-o", "--output", help="Where to store the recovered payload")
    extract.add_argument("--password", "--pw", help="Password used to decrypt the payload")
    extract.add_argument(
        "--technique",
        "--tech",
        choices=["auto", "lsb", "pvd", "dct", "append", "exif", "id3", "audio_lsb", "video_lsb"],
        help="Technique hint to speed up extraction",
    )
    extract.add_argument("--openpgp", help="OpenPGP key identifier (reserved for future use)")

    # ------------------------------------------------------------------
    # Analyze command
    # ------------------------------------------------------------------
    analyze = subparsers.add_parser(
        "analyze",
        help="Assess a file for steganographic artefacts",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    analyze.add_argument("-i", "--input", required=True, help="File to analyse")
    analyze.add_argument(
        "-M",
        "--method",
        choices=["all", "chi-square", "histogram", "ela", "ml"],
        default="all",
        help="Analysis method to use",
    )
    analyze.add_argument("-v", "--verbose", action="store_true", help="Show detailed insights")

    return parser.parse_args(args=list(argv) if argv is not None else None)


def run_gui() -> None:
    """Launch the graphical user interface."""

    try:
        logger.info("Starting STEGOSIGHT in GUI mode")
        from PyQt5.QtWidgets import QApplication

        from gui import STEGOSIGHTApp

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)

        window = STEGOSIGHTApp()
        window.show()

        logger.info("GUI initialized successfully")
        sys.exit(app.exec_())
    except ImportError as exc:
        logger.error("Failed to import GUI modules: %s", exc)
        print("Error: ไม่สามารถโหลด GUI ได้ กรุณาติดตั้ง PyQt5")
        print("  pip install PyQt5")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Unexpected error in GUI mode", exc_info=True)
        print(f"Error: เกิดข้อผิดพลาดในการเรียกใช้ GUI - {exc}")
        sys.exit(1)


def run_cli(args) -> None:
    """Execute a CLI command."""

    try:
        if getattr(args, "command", None) is None:
            raise ValueError("No CLI command provided")

        from cli import StegosightCLI

        cli = StegosightCLI(args)
        success = cli.run()
        sys.exit(0 if success else 1)
    except ImportError as exc:
        logger.error("Failed to import CLI modules: %s", exc)
        print(f"Error: ไม่สามารถโหลด CLI modules ได้ - {exc}")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Unexpected error in CLI mode", exc_info=True)
        print(f"Error: เกิดข้อผิดพลาดในการเรียกใช้ CLI - {exc}")
        sys.exit(1)


def check_dependencies() -> None:
    """Check optional runtime dependencies and log warnings if missing."""

    required_packages = {
        "numpy": "NumPy",
        "PIL": "Pillow",
        "cv2": "OpenCV",
        "cryptography": "cryptography",
    }

    missing_packages = []
    for package, name in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(name)

    if missing_packages:
        logger.warning("Missing packages: %s", ", ".join(missing_packages))
        print("Warning: แพ็คเกจต่อไปนี้ยังไม่ได้ติดตั้ง:")
        for package in missing_packages:
            print(f"  - {package}")


def main(argv: Optional[Iterable[str]] = None) -> None:
    """Main entry point used by ``python -m`` and executable scripts."""

    args = parse_arguments(argv)
    command = getattr(args, "command", None)

    if command is None:
        run_gui()
        return

    run_cli(args)


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
