"""
STEGOSIGHT - Main Entry Point
Stego & Anti-Stego Intelligent Guard

จุดเริ่มต้นของโปรแกรม รองรับทั้ง GUI และ CLI mode
"""

import sys
import argparse
from pathlib import Path

# Import configuration
from config import APP_NAME, APP_VERSION, APP_DESCRIPTION

# Import logging utility
from utils.logger import setup_logger

# Setup logger
logger = setup_logger(__name__)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f"{APP_DESCRIPTION} v{APP_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--cli',
        action='store_true',
        help='เรียกใช้งานในโหมด Command Line Interface'
    )
    
    parser.add_argument(
        '--mode',
        choices=['embed', 'extract', 'analyze', 'neutralize'],
        help='โหมดการทำงาน (สำหรับ CLI)'
    )
    
    parser.add_argument(
        '--cover',
        type=str,
        help='ไฟล์ต้นฉบับ (Cover file)'
    )
    
    parser.add_argument(
        '--secret',
        type=str,
        help='ไฟล์ข้อมูลลับ (Secret data)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='ไฟล์ผลลัพธ์ (Output file)'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        help='รหัสผ่านสำหรับเข้ารหัส/ถอดรหัส'
    )
    
    parser.add_argument(
        '--method',
        choices=['lsb', 'pvd', 'dct', 'adaptive'],
        default='adaptive',
        help='วิธีการซ่อนข้อมูล (default: adaptive)'
    )
    
    parser.add_argument(
        '--analysis-method',
        choices=['chi-square', 'histogram', 'ela', 'ml', 'all'],
        default='all',
        help='วิธีการวิเคราะห์ (default: all)'
    )
    
    parser.add_argument(
        '--no-analysis',
        action='store_true',
        help='ข้ามการวิเคราะห์ความเสี่ยงอัตโนมัติ'
    )
    
    parser.add_argument(
        '--neutralize-method',
        choices=['metadata', 'recompress', 'transform', 'all'],
        help='วิธีการทำให้เป็นกลาง'
    )
    
    parser.add_argument(
        '--batch',
        type=str,
        help='โฟลเดอร์สำหรับประมวลผลแบบ batch'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='แสดงข้อมูลการทำงานแบบละเอียด'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'{APP_NAME} v{APP_VERSION}'
    )
    
    return parser.parse_args()


def run_gui():
    """Run GUI mode"""
    try:
        logger.info("Starting STEGOSIGHT in GUI mode")
        
        # Import GUI module
        from gui import STEGOSIGHTApp
        from PyQt5.QtWidgets import QApplication
        
        # Create QApplication
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        
        # Create and show main window
        window = STEGOSIGHTApp()
        window.show()
        
        logger.info("GUI initialized successfully")
        
        # Start event loop
        sys.exit(app.exec_())
        
    except ImportError as e:
        logger.error(f"Failed to import GUI modules: {e}")
        print(f"Error: ไม่สามารถโหลด GUI ได้ กรุณาติดตั้ง PyQt5")
        print(f"  pip install PyQt5")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in GUI mode: {e}", exc_info=True)
        print(f"Error: เกิดข้อผิดพลาดในการเรียกใช้ GUI - {e}")
        sys.exit(1)


def run_cli(args):
    """Run CLI mode"""
    try:
        logger.info("Starting STEGOSIGHT in CLI mode")
        
        # Import CLI module
        from cli import STEGOSIGHTCLI
        
        # Create CLI instance
        cli = STEGOSIGHTCLI(args)
        
        # Run CLI
        result = cli.run()
        
        if result:
            logger.info("CLI operation completed successfully")
            sys.exit(0)
        else:
            logger.error("CLI operation failed")
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"Failed to import CLI modules: {e}")
        print(f"Error: ไม่สามารถโหลด CLI modules ได้ - {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in CLI mode: {e}", exc_info=True)
        print(f"Error: เกิดข้อผิดพลาดในการเรียกใช้ CLI - {e}")
        sys.exit(1)


def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = {
        'numpy': 'NumPy',
        'PIL': 'Pillow',
        'cv2': 'OpenCV',
        'cryptography': 'cryptography'
    }
    
    missing_packages = []
    
    for package, name in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(name)
    
    if missing_packages:
        logger.warning(f"Missing packages: {', '.join(missing_packages)}")
        print(f"Warning: แพ็คเกจต่อไปนี้ยังไม่ได้ติดตั้ง:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print(f"\nกรุณาติดตั้งด้วยคำสั่ง:")
        print(f"  pip install numpy pillow opencv-python cryptography")
        return False
    
    return True


def main():
    """Main entry point"""
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Setup logging level
        if args.verbose:
            logger.setLevel('DEBUG')
            logger.debug("Verbose mode enabled")
        
        # Log startup
        logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        
        # Check dependencies
        if not check_dependencies():
            logger.error("Missing required dependencies")
            print("\nโปรแกรมไม่สามารถทำงานได้เนื่องจากขาดแพ็คเกจที่จำเป็น")
            sys.exit(1)
        
        # Decide mode: CLI or GUI
        if args.cli or args.mode:
            # CLI mode
            if not args.mode:
                print("Error: กรุณาระบุ --mode เมื่อใช้งานในโหมด CLI")
                print("Example: python main.py --cli --mode embed --cover image.png --secret secret.txt")
                sys.exit(1)
            run_cli(args)
        else:
            # GUI mode (default)
            run_gui()
            
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
        print("\n\nโปรแกรมถูกหยุดโดยผู้ใช้")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Critical error in main: {e}", exc_info=True)
        print(f"\nError: เกิดข้อผิดพลาดร้ายแรง - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()