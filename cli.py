"""
STEGOSIGHT CLI - Command Line Interface
ส่วนติดต่อผู้ใช้แบบ Command Line
"""

import sys
from pathlib import Path
from getpass import getpass
from utils.logger import setup_logger
from config import APP_NAME, APP_VERSION

logger = setup_logger(__name__)


class STEGOSIGHTCLI:
    """Command Line Interface สำหรับ STEGOSIGHT"""
    
    def __init__(self, args):
        """
        Initialize CLI
        
        Args:
            args: Parsed command line arguments
        """
        self.args = args
        self.mode = args.mode
        logger.info(f"CLI initialized in {self.mode} mode")
    
    def run(self):
        """
        Run CLI operation
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.mode == 'embed':
                return self.embed()
            elif self.mode == 'extract':
                return self.extract()
            elif self.mode == 'analyze':
                return self.analyze()
            elif self.mode == 'neutralize':
                return self.neutralize()
            else:
                print(f"Error: Unknown mode '{self.mode}'")
                return False
        except Exception as e:
            logger.error(f"CLI operation failed: {e}", exc_info=True)
            print(f"\nError: {e}")
            return False
    
    def embed(self):
        """ซ่อนข้อมูล (Embed mode)"""
        print(f"\n{'='*60}")
        print(f"  {APP_NAME} - EMBED MODE")
        print(f"{'='*60}\n")
        
        # Validate inputs
        if not self.args.cover:
            print("Error: --cover is required")
            return False
        
        if not self.args.secret:
            print("Error: --secret is required")
            return False
        
        cover_path = Path(self.args.cover)
        secret_path = Path(self.args.secret)
        
        if not cover_path.exists():
            print(f"Error: Cover file not found: {cover_path}")
            return False
        
        if not secret_path.exists():
            print(f"Error: Secret file not found: {secret_path}")
            return False
        
        # Load secret data
        print(f"[1/5] Loading files...")
        with open(secret_path, 'rb') as f:
            secret_data = f.read()
        print(f"  ✓ Cover file: {cover_path.name} ({cover_path.stat().st_size / 1024:.2f} KB)")
        print(f"  ✓ Secret data: {secret_path.name} ({len(secret_data)} bytes)")
        
        # Get password if needed
        password = self.args.password
        if not password:
            use_encryption = input("\nUse encryption? (y/n) [y]: ").lower()
            if use_encryption != 'n':
                password = getpass("Enter password: ")
                confirm = getpass("Confirm password: ")
                if password != confirm:
                    print("Error: Passwords do not match")
                    return False
        
        # Encrypt data if password provided
        if password:
            print(f"\n[2/5] Encrypting data...")
            from cryptography_module.encryption import encrypt_data
            secret_data = encrypt_data(secret_data, password)
            print(f"  ✓ Data encrypted ({len(secret_data)} bytes)")
        else:
            print(f"\n[2/5] Skipping encryption...")
        
        # Select method
        method = self.args.method
        print(f"\n[3/5] Embedding data using {method} method...")
        
        # Embed
        from steganography.adaptive import AdaptiveSteganography
        stego = AdaptiveSteganography()
        
        output_path = self.args.output
        if not output_path:
            output_path = cover_path.parent / f"{cover_path.stem}_stego{cover_path.suffix}"
        
        stego_path = stego.embed(cover_path, secret_data, method, output_path)
        print(f"  ✓ Data embedded successfully")
        print(f"  ✓ Output: {stego_path}")
        
        # Analyze risk if not disabled
        if not self.args.no_analysis:
            print(f"\n[4/5] Analyzing risk...")
            from steganalysis.risk_scoring import RiskScorer
            scorer = RiskScorer()
            risk_result = scorer.calculate_risk(stego_path)
            
            print(f"  ✓ Risk Score: {risk_result['score']}/100 ({risk_result['level']})")
            print(f"  {risk_result['recommendation']}")
            
            if risk_result['score'] > 70:
                neutralize = input("\nHigh risk detected. Neutralize? (y/n) [y]: ").lower()
                if neutralize != 'n':
                    print(f"\n[5/5] Neutralizing...")
                    from neutralization.metadata import strip_metadata
                    from neutralization.recompression import recompress_file
                    
                    stego_path = strip_metadata(stego_path)
                    stego_path = recompress_file(stego_path)
                    print(f"  ✓ Neutralization complete")
        else:
            print(f"\n[4/5] Skipping analysis...")
        
        print(f"\n{'='*60}")
        print(f"  ✓ EMBEDDING COMPLETE")
        print(f"  Output file: {stego_path}")
        print(f"{'='*60}\n")
        
        return True
    
    def extract(self):
        """ดึงข้อมูล (Extract mode)"""
        print(f"\n{'='*60}")
        print(f"  {APP_NAME} - EXTRACT MODE")
        print(f"{'='*60}\n")
        
        # Validate inputs
        if not self.args.cover:
            print("Error: --cover (stego file) is required")
            return False
        
        stego_path = Path(self.args.cover)
        
        if not stego_path.exists():
            print(f"Error: Stego file not found: {stego_path}")
            return False
        
        print(f"[1/3] Loading stego file...")
        print(f"  ✓ File: {stego_path.name} ({stego_path.stat().st_size / 1024:.2f} KB)")
        
        # Extract
        print(f"\n[2/3] Extracting data using {self.args.method} method...")
        
        from steganography.adaptive import AdaptiveSteganography
        stego = AdaptiveSteganography()
        
        extracted_data = stego.extract(stego_path, self.args.method)
        print(f"  ✓ Data extracted ({len(extracted_data)} bytes)")
        
        # Decrypt if password provided
        password = self.args.password
        if not password:
            decrypt = input("\nIs data encrypted? (y/n) [y]: ").lower()
            if decrypt != 'n':
                password = getpass("Enter password: ")
        
        if password:
            print(f"\n[3/3] Decrypting data...")
            from cryptography_module.encryption import decrypt_data
            try:
                extracted_data = decrypt_data(extracted_data, password)
                print(f"  ✓ Data decrypted ({len(extracted_data)} bytes)")