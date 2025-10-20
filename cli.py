"""
STEGOSIGHT CLI - Command Line Interface
ส่วนติดต่อผู้ใช้แบบ Command Line
"""

from getpass import getpass
from pathlib import Path
from typing import List

from config import APP_NAME, APP_VERSION
from utils.logger import setup_logger

logger = setup_logger(__name__)


class STEGOSIGHTCLI:
    """Command Line Interface สำหรับ STEGOSIGHT"""

    def __init__(self, args):
        """Initialize CLI with parsed arguments."""
        self.args = args
        self.mode = args.mode
        logger.info(f"CLI initialized in {self.mode} mode")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def run(self):
        """Run CLI operation."""
        try:
            if self.mode == "embed":
                return self.embed()
            if self.mode == "extract":
                return self.extract()
            if self.mode == "analyze":
                return self.analyze()
            if self.mode == "neutralize":
                return self.neutralize()
            print(f"Error: Unknown mode '{self.mode}'")
            return False
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return False
        except Exception as exc:  # pragma: no cover - defensive safety
            logger.error("CLI operation failed", exc_info=True)
            print(f"\nError: {exc}")
            return False

    # ------------------------------------------------------------------
    # Embed mode
    # ------------------------------------------------------------------
    def embed(self):
        """ซ่อนข้อมูล (Embed mode)"""
        print(f"\n{'=' * 60}")
        print(f"  {APP_NAME} v{APP_VERSION} - EMBED MODE")
        print(f"{'=' * 60}\n")

        if not self.args.cover or not self.args.secret:
            print("Error: --cover และ --secret จำเป็นต้องระบุ")
            return False

        cover_path = Path(self.args.cover)
        secret_path = Path(self.args.secret)

        if not cover_path.exists():
            print(f"Error: Cover file not found: {cover_path}")
            return False
        if not secret_path.exists():
            print(f"Error: Secret file not found: {secret_path}")
            return False

        print("[1/5] Loading files…")
        with open(secret_path, "rb") as handle:
            secret_data = handle.read()
        print(f"  ✓ Cover file: {cover_path.name} ({cover_path.stat().st_size / 1024:.2f} KB)")
        print(f"  ✓ Secret data: {secret_path.name} ({len(secret_data)} bytes)")

        password = self.args.password
        if not password:
            use_encryption = input("\nUse encryption? (y/n) [y]: ").strip().lower()
            if use_encryption != "n":
                password = getpass("Enter password: ")
                confirm = getpass("Confirm password: ")
                if password != confirm:
                    print("Error: Passwords do not match")
                    return False

        if password:
            print("\n[2/5] Encrypting data…")
            from cryptography_module.encryption import encrypt_data

            secret_data = encrypt_data(secret_data, password)
            print(f"  ✓ Data encrypted ({len(secret_data)} bytes)")
        else:
            print("\n[2/5] Skipping encryption…")

        method = self.args.method
        print(f"\n[3/5] Embedding data using {method} method…")
        from steganography_module.adaptive import AdaptiveSteganography

        stego = AdaptiveSteganography()
        output_path = Path(self.args.output) if self.args.output else None
        if output_path is None:
            output_path = cover_path.parent / f"{cover_path.stem}_stego{cover_path.suffix}"

        stego_path = Path(stego.embed(cover_path, secret_data, method, output_path))
        print("  ✓ Data embedded successfully")
        print(f"  ✓ Output: {stego_path}")

        if not self.args.no_analysis:
            print("\n[4/5] Analyzing risk…")
            from steganalysis_module.risk_scoring import RiskScorer

            scorer = RiskScorer()
            risk_result = scorer.calculate_risk(stego_path)
            print(f"  ✓ Risk Score: {risk_result['score']}/100 ({risk_result['level']})")
            print(f"  {risk_result['recommendation']}")

            if risk_result.get("score", 0) > 70:
                neutralize = input("\nHigh risk detected. Neutralize? (y/n) [y]: ").lower()
                if neutralize != "n":
                    print("\n[5/5] Neutralizing…")
                    from neutralization.metadata import strip_metadata
                    from neutralization.recompression import recompress_file

                    cleaned = Path(strip_metadata(stego_path))
                    final = Path(recompress_file(cleaned))
                    stego_path = final
                    print("  ✓ Neutralization complete")
        else:
            print("\n[4/5] Skipping analysis…")

        print(f"\n{'=' * 60}")
        print("  ✓ EMBEDDING COMPLETE")
        print(f"  Output file: {stego_path}")
        print(f"{'=' * 60}\n")
        return True

    # ------------------------------------------------------------------
    # Extract mode
    # ------------------------------------------------------------------
    def extract(self):
        """ดึงข้อมูล (Extract mode)"""
        print(f"\n{'=' * 60}")
        print(f"  {APP_NAME} v{APP_VERSION} - EXTRACT MODE")
        print(f"{'=' * 60}\n")

        if not self.args.cover:
            print("Error: --cover (stego file) is required")
            return False

        stego_path = Path(self.args.cover)
        if not stego_path.exists():
            print(f"Error: Stego file not found: {stego_path}")
            return False

        print("[1/3] Loading stego file…")
        print(f"  ✓ File: {stego_path.name} ({stego_path.stat().st_size / 1024:.2f} KB)")

        print(f"\n[2/3] Extracting data using {self.args.method} method…")
        from steganography_module.adaptive import AdaptiveSteganography

        stego = AdaptiveSteganography()
        extracted_data = stego.extract(stego_path, self.args.method)
        print(f"  ✓ Data extracted ({len(extracted_data)} bytes)")

        password = self.args.password
        if not password:
            decrypt = input("\nIs data encrypted? (y/n) [y]: ").strip().lower()
            if decrypt != "n":
                password = getpass("Enter password: ")

        if password:
            print("\n[3/3] Decrypting data…")
            from cryptography_module.encryption import decrypt_data

            try:
                extracted_data = decrypt_data(extracted_data, password)
                print(f"  ✓ Data decrypted ({len(extracted_data)} bytes)")
            except Exception as exc:
                logger.error("Failed to decrypt data", exc_info=True)
                print(f"  ✗ Failed to decrypt data: {exc}")
                return False
        else:
            print("\n[3/3] Skipping decryption…")

        output_path = Path(self.args.output) if self.args.output else None
        if output_path is None:
            output_path = stego_path.parent / f"{stego_path.stem}_extracted.bin"

        with open(output_path, "wb") as handle:
            handle.write(extracted_data)
        print(f"\nData written to: {output_path} ({len(extracted_data)} bytes)")

        print(f"\n{'=' * 60}")
        print("  ✓ EXTRACTION COMPLETE")
        print(f"  Output file: {output_path}")
        print(f"{'=' * 60}\n")
        return True

    # ------------------------------------------------------------------
    # Analyze mode
    # ------------------------------------------------------------------
    def analyze(self):
        """วิเคราะห์ความเสี่ยงของไฟล์"""
        print(f"\n{'=' * 60}")
        print(f"  {APP_NAME} v{APP_VERSION} - ANALYZE MODE")
        print(f"{'=' * 60}\n")

        if not self.args.cover:
            print("Error: --cover (file to analyze) is required")
            return False

        file_path = Path(self.args.cover)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            return False

        print("[1/2] Running analysis…")
        from steganalysis_module.risk_scoring import RiskScorer

        scorer = RiskScorer()
        methods = [self.args.analysis_method] if self.args.analysis_method else ["all"]
        result = scorer.analyze_file(file_path, methods)

        print(f"\n[2/2] Analysis complete")
        print(f"  ✓ Risk Score: {result.get('score')} / 100")
        print(f"  ✓ Level: {result.get('level')}")
        if result.get("recommendation"):
            print(f"  Recommendation: {result['recommendation']}")

        details = result.get("details", {})
        if details:
            print("\nMethod scores:")
            for method, score in details.items():
                print(f"  - {method}: {score}")

        errors = result.get("errors", {})
        if errors:
            print("\nWarnings:")
            for method, message in errors.items():
                print(f"  - {method}: {message}")

        print(f"\n{'=' * 60}")
        print("  ✓ ANALYSIS COMPLETE")
        print(f"{'=' * 60}\n")
        return True

    # ------------------------------------------------------------------
    # Neutralize mode
    # ------------------------------------------------------------------
    def neutralize(self):
        """ทำให้ไฟล์เป็นกลาง (ลดความเสี่ยงการถูกตรวจจับ)"""
        print(f"\n{'=' * 60}")
        print(f"  {APP_NAME} v{APP_VERSION} - NEUTRALIZE MODE")
        print(f"{'=' * 60}\n")

        if not self.args.cover:
            print("Error: --cover (file to neutralize) is required")
            return False

        file_path = Path(self.args.cover)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            return False

        methods = self._resolve_neutralize_methods()
        if not methods:
            print("Error: No neutralization methods selected")
            return False

        print(f"[1/{len(methods)+1}] Starting neutralization pipeline…")
        current_path = file_path

        from neutralization.metadata import strip_metadata
        from neutralization.recompression import recompress_file
        from neutralization.transform import apply_transforms

        for index, method in enumerate(methods, start=1):
            is_last = index == len(methods)
            target = Path(self.args.output) if is_last and self.args.output else None

            if method == "metadata":
                print(f"  → Step {index}/{len(methods)}: Stripping metadata…")
                current_path = Path(strip_metadata(current_path, target))
            elif method == "recompress":
                print(f"  → Step {index}/{len(methods)}: Re-compressing file…")
                current_path = Path(recompress_file(current_path, target))
            elif method == "transform":
                print(f"  → Step {index}/{len(methods)}: Applying transforms…")
                current_path = Path(apply_transforms(current_path, target))
            else:
                print(f"  ! Unknown method skipped: {method}")

        print(f"\n[{len(methods)+1}/{len(methods)+1}] Neutralization complete")
        print(f"  ✓ Output: {current_path}")

        print(f"\n{'=' * 60}")
        print("  ✓ NEUTRALIZATION COMPLETE")
        print(f"{'=' * 60}\n")
        return True

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _resolve_neutralize_methods(self) -> List[str]:
        method = self.args.neutralize_method
        if not method or method == "all":
            return ["metadata", "recompress", "transform"]
        return [method]
