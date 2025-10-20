"""Command line interface for STEGOSIGHT.

This module implements the command dispatcher used by :mod:`main`.  The
interface follows the design described in the project brief: a top-level
``stegosight`` command with dedicated sub-commands for hiding, extracting and
analysing data.  The CLI reuses the same backend components as the GUI so that
behaviour is consistent for both user groups (general users via the GUI and
power users via the CLI).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from config import APP_NAME, APP_VERSION
from utils.logger import setup_logger
from utils.payloads import create_file_payload, create_text_payload, unpack_payload

logger = setup_logger(__name__)


IMAGE_EXTENSIONS: Tuple[str, ...] = (".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg")
AUDIO_EXTENSIONS: Tuple[str, ...] = (".wav", ".flac")
VIDEO_EXTENSIONS: Tuple[str, ...] = (".mp4", ".avi", ".mkv", ".mov")


class CLIError(RuntimeError):
    """Custom error raised for recoverable CLI failures."""


@dataclass
class PayloadInfo:
    """Information about a prepared payload blob."""

    blob: bytes
    kind: str
    name: Optional[str]


def _detect_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return "unknown"


def _ensure_exists(path: Path, description: str) -> Path:
    if not path.exists():
        raise CLIError(f"{description} not found: {path}")
    return path


class StegosightCLI:
    """CLI dispatcher for STEGOSIGHT."""

    def __init__(self, args) -> None:
        self.args = args
        self.command = getattr(args, "command", None)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def run(self) -> bool:
        try:
            if self.command == "hide":
                self._handle_hide()
            elif self.command == "extract":
                self._handle_extract()
            elif self.command == "analyze":
                self._handle_analyze()
            else:
                raise CLIError("No command specified. Use --help for usage information.")
        except CLIError as exc:
            logger.error("CLI error: %s", exc)
            print(f"Error: {exc}")
            return False
        except KeyboardInterrupt:
            print("Operation cancelled by user.")
            return False
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Unhandled CLI exception")
            print(f"Unexpected error: {exc}")
            return False

        return True

    # ------------------------------------------------------------------
    # Hide command
    # ------------------------------------------------------------------
    def _handle_hide(self) -> None:
        args = self.args

        cover_path = _ensure_exists(Path(args.carrier), "Carrier file")
        payload = self._prepare_payload(args, cover_path)
        recommendation_source = payload.blob

        password = args.password
        if password:
            from cryptography_module.encryption import encrypt_data

            payload = PayloadInfo(
                blob=encrypt_data(payload.blob, password),
                kind=payload.kind,
                name=payload.name,
            )

        media_type = _detect_media_type(cover_path)
        method, media_type = self._resolve_hide_method(args, media_type)

        output_path = Path(args.output) if args.output else None
        stego_path = self._execute_hide(cover_path, payload, method, media_type, output_path)

        print(f"\n{APP_NAME} v{APP_VERSION} - Hide")
        print(f"Carrier : {cover_path}")
        print(f"Output  : {stego_path}")
        print(f"Method  : {method}")

        if password:
            print("Encryption: AES-256-GCM (password protected)")

        if getattr(args, "openpgp", None):
            print("Note: OpenPGP integration is not implemented in this build.")

        if not getattr(args, "no_analysis", False) and media_type == "image":
            from steganalysis_module.risk_scoring import RiskScorer

            scorer = RiskScorer()
            result = scorer.calculate_risk(stego_path)
            print("\nRisk Assessment")
            print(f"  Score : {result.get('score')}/100")
            print(f"  Level : {result.get('level')}")
            if result.get("recommendation"):
                print(f"  Advice: {result['recommendation']}")

        if media_type == "image" and method in {"auto", "adaptive", "lsb", "pvd", "dct"}:
            try:
                from steganography_module.adaptive import AdaptiveSteganography

                engine = AdaptiveSteganography()
                settings = engine.get_recommended_settings(cover_path, recommendation_source)
            except Exception as exc:  # pragma: no cover - best-effort recommendation
                logger.debug("Failed to compute recommendations: %s", exc)
            else:
                print("\nEmbedding Summary")
                print(f"  Capacity       : {settings['capacity']} bytes")
                print(f"  Data size      : {settings['data_size']} bytes")
                print(f"  Embedding rate : {settings['embedding_rate']:.2f}%")
                print(f"  Complexity     : {settings['complexity']:.2f}")
                print(f"  Risk level     : {settings['risk_level']}")
                print(f"  Recommendation : {settings['recommendation']}")

    def _prepare_payload(self, args, cover_path: Path) -> PayloadInfo:
        if args.payload and args.text:
            raise CLIError("--payload and --text cannot be used together")
        if not args.payload and not args.text:
            raise CLIError("Either --payload or --text must be provided")

        if args.payload:
            payload_path = _ensure_exists(Path(args.payload), "Payload file")
            payload_bytes = payload_path.read_bytes()
            blob = create_file_payload(
                payload_bytes,
                name=payload_path.name,
                encrypted=bool(args.password),
            )
            return PayloadInfo(blob=blob, kind="file", name=payload_path.name)

        text = args.text or ""
        blob = create_text_payload(text, encrypted=bool(args.password))
        default_name = f"{cover_path.stem}_message.txt"
        return PayloadInfo(blob=blob, kind="text", name=default_name)

    def _resolve_hide_method(self, args, media_type: str) -> Tuple[str, str]:
        mode = getattr(args, "mode", "auto") or "auto"
        technique = getattr(args, "technique", None)

        if media_type == "unknown":
            raise CLIError("Unsupported carrier type. Supported: images, WAV audio, MP4/AVI video")

        if mode == "manual":
            if not technique:
                raise CLIError("Manual mode requires --technique")
            technique = technique.lower()
            if technique in {"lsb", "pvd", "dct", "append", "audio_lsb", "video_lsb"}:
                return technique, media_type
            if technique == "exif":
                if media_type != "image":
                    raise CLIError("EXIF technique is only available for image carriers")
                return "exif", media_type
            if technique == "id3":
                if media_type != "audio":
                    raise CLIError("ID3 technique is only available for audio carriers")
                return "id3", media_type
            raise CLIError(f"Unsupported technique: {technique}")

        if technique and mode != "manual":
            return technique.lower(), media_type

        if media_type == "audio":
            return "audio_lsb", "audio"
        if media_type == "video":
            return "video_lsb", "video"
        return "auto", "image"

    def _execute_hide(
        self,
        cover_path: Path,
        payload: PayloadInfo,
        method: str,
        media_type: str,
        output_path: Optional[Path],
    ) -> Path:
        if method == "append":
            from steganography_module.appender import append_payload_to_file

            result = append_payload_to_file(
                cover_path,
                payload.blob,
                output_path=output_path,
                payload_name=payload.name,
            )
            return Path(result)

        if method == "exif":
            try:
                from steganography_module.png_chunks import embed_data_in_chunk
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise CLIError("PNG metadata embedding backend is unavailable") from exc

            if cover_path.suffix.lower() != ".png":
                raise CLIError("EXIF embedding currently supports PNG files only")

            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".stegopayload") as temp:
                temp.write(payload.blob)
                temp.flush()
                temp_path = Path(temp.name)
            try:
                result = embed_data_in_chunk(
                    cover_path,
                    temp_path,
                    output_filepath=output_path,
                )
            finally:
                temp_path.unlink(missing_ok=True)
            return Path(result)

        if media_type == "audio":
            from steganography_module.audio import AudioSteganography

            engine = AudioSteganography()
            result = engine.embed(cover_path, payload.blob, output_path=output_path)
            return Path(result)

        if media_type == "video":
            from steganography_module.video import VideoSteganography

            engine = VideoSteganography()
            result = engine.embed(cover_path, payload.blob, output_path=output_path)
            return Path(result)

        from steganography_module.adaptive import AdaptiveSteganography

        engine = AdaptiveSteganography()
        result = engine.embed(
            cover_path,
            payload.blob,
            method,
            output_path=output_path,
        )
        return Path(result)

    # ------------------------------------------------------------------
    # Extract command
    # ------------------------------------------------------------------
    def _handle_extract(self) -> None:
        args = self.args

        stego_path = _ensure_exists(Path(args.input), "Input file")
        password = args.password

        media_type = _detect_media_type(stego_path)
        method_hint = getattr(args, "technique", None)

        data, used_method = self._execute_extract(stego_path, media_type, method_hint)

        if password:
            from cryptography_module.encryption import decrypt_data

            try:
                data = decrypt_data(data, password)
            except Exception as exc:
                raise CLIError("Unable to decrypt payload: incorrect password or corrupted data") from exc

        payload_info = self._decode_payload(data)

        output_path = self._write_extracted_payload(payload_info, stego_path, getattr(args, "output", None))

        print(f"\n{APP_NAME} v{APP_VERSION} - Extract")
        print(f"Source : {stego_path}")
        print(f"Method : {used_method}")
        if output_path:
            print(f"Saved  : {output_path}")
        if payload_info.kind == "text" and not output_path:
            print("\nRecovered message:\n")
            print(payload_info.text)

        if getattr(args, "openpgp", None):
            print("Note: OpenPGP integration is not implemented in this build.")

    def _execute_extract(
        self,
        stego_path: Path,
        media_type: str,
        method_hint: Optional[str],
    ) -> Tuple[bytes, str]:
        if method_hint:
            method_hint = method_hint.lower()

        from steganography_module.appender import extract_appended_payload, has_appended_payload

        append_requested = method_hint == "append"
        if method_hint in {None, "auto"} and has_appended_payload(stego_path):
            append_requested = True

        if append_requested or media_type == "unknown":
            payload = extract_appended_payload(stego_path)
            return payload if isinstance(payload, bytes) else bytes(payload), "append"

        if media_type == "audio" or method_hint in {"id3", "audio_lsb"}:
            from steganography_module.audio import AudioSteganography

            engine = AudioSteganography()
            payload = engine.extract(stego_path)
            return payload, "audio_lsb"

        if media_type == "video" or method_hint == "video_lsb":
            from steganography_module.video import VideoSteganography

            engine = VideoSteganography()
            payload = engine.extract(stego_path)
            return payload, "video_lsb"

        if method_hint == "exif":
            try:
                from steganography_module.png_chunks import extract_data_from_chunk
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise CLIError("PNG metadata extraction backend is unavailable") from exc

            extracted_path = Path(
                extract_data_from_chunk(
                    stego_path,
                    output_dir=stego_path.parent,
                    prefix="stegosight_",
                    overwrite=True,
                )
            )
            data = extracted_path.read_bytes()
            extracted_path.unlink(missing_ok=True)
            return data, "exif"

        from steganography_module.adaptive import AdaptiveSteganography

        engine = AdaptiveSteganography()
        method = method_hint or "auto"
        data = engine.extract(stego_path, method)
        used_method = getattr(engine, "last_method", method)
        return data, used_method

    def _decode_payload(self, data: bytes):
        class _DecodedPayload:
            __slots__ = ("kind", "metadata", "data", "text")

            def __init__(self, info: Dict[str, object]):
                self.kind = str(info.get("kind", "binary"))
                self.metadata = dict(info.get("metadata", {}))
                self.data = info.get("data", b"")
                self.text = info.get("text")

        try:
            info = unpack_payload(data)
        except Exception as exc:
            raise CLIError(f"Recovered payload is not a valid STEGOSIGHT package: {exc}") from exc

        return _DecodedPayload(info)

    def _write_extracted_payload(
        self,
        payload,
        stego_path: Path,
        output_arg: Optional[str],
    ) -> Optional[Path]:
        if payload.kind == "text" and payload.text is None:
            payload.text = payload.data.decode("utf-8", errors="replace")

        if payload.kind == "text" and not output_arg:
            return None

        if payload.kind == "text":
            destination = Path(output_arg or stego_path.with_suffix(".txt"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(str(payload.text or ""), encoding=payload.metadata.get("encoding", "utf-8"))
            return destination

        filename = payload.metadata.get("name") or payload.metadata.get("filename")
        if output_arg:
            destination = Path(output_arg)
            if destination.is_dir():
                destination = destination / (filename or f"{stego_path.stem}_payload.bin")
        else:
            destination = stego_path.parent / (filename or f"{stego_path.stem}_payload.bin")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(bytes(payload.data))
        return destination

    # ------------------------------------------------------------------
    # Analyze command
    # ------------------------------------------------------------------
    def _handle_analyze(self) -> None:
        args = self.args

        target = _ensure_exists(Path(args.input), "Input file")
        methods = [args.method] if args.method and args.method != "all" else ["all"]

        from steganalysis_module.risk_scoring import RiskScorer

        scorer = RiskScorer()
        result = scorer.analyze_file(target, methods)

        print(f"\n{APP_NAME} v{APP_VERSION} - Analyze")
        print(f"Target : {target}")
        print(f"Score  : {result.get('score')} / 100")
        print(f"Level  : {result.get('level')}")
        if result.get("recommendation"):
            print(f"Advice : {result['recommendation']}")

        details = result.get("details", {})
        if details:
            print("\nMethod Scores:")
            for name, score in details.items():
                print(f"  - {name}: {score}")

        if args.verbose and result.get("insights"):
            print("\nInsights:")
            for insight in result["insights"]:
                print(f"  * {insight}")

        if result.get("errors"):
            print("\nWarnings:")
            for name, message in result["errors"].items():
                print(f"  - {name}: {message}")


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Entry point used by unit tests."""

    from main import parse_arguments  # Lazy import to avoid circular dependency.

    args = parse_arguments(list(argv) if argv is not None else None)
    cli = StegosightCLI(args)
    return 0 if cli.run() else 1


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    sys.exit(main(sys.argv[1:]))
