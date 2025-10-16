"""
LSB (Least Significant Bit) Matching Steganography
วิธีการซ่อนข้อมูลโดยการแก้ไข LSB ของพิกเซล
"""

import numpy as np
from PIL import Image
import random
from pathlib import Path
from utils.logger import setup_logger, log_operation

logger = setup_logger(__name__)


class LSBSteganography:
    """LSB Matching Steganography Implementation"""
    
    def __init__(self, bits_per_channel=1, mode='adaptive'):
        """
        Initialize LSB steganography
        
        Args:
            bits_per_channel: จำนวนบิตที่จะใช้ต่อ channel (1-4)
            mode: โหมดการซ่อน ('sequential', 'random', 'adaptive')
        """
        self.bits_per_channel = min(max(1, bits_per_channel), 4)
        self.mode = mode
        logger.debug(f"LSB initialized: bits={bits_per_channel}, mode={mode}")
    
    @log_operation("LSB Embed")
    def embed(self, cover_path, secret_data, output_path=None):
        """
        ซ่อนข้อมูลลงในภาพ
        
        Args:
            cover_path: path ของภาพต้นฉบับ
            secret_data: ข้อมูลที่จะซ่อน (bytes)
            output_path: path สำหรับบันทึกภาพผลลัพธ์
        
        Returns:
            str: path ของภาพที่มีข้อมูลซ่อนอยู่
        """
        # Load image
        cover_path = Path(cover_path)
        image = Image.open(cover_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            logger.info(f"Converting image from {image.mode} to RGB")
            image = image.convert('RGB')
        
        # Get image data
        pixels = np.array(image)
        height, width, channels = pixels.shape
        
        # Calculate capacity
        max_bytes = (height * width * channels * self.bits_per_channel) // 8
        logger.info(f"Image capacity: {max_bytes} bytes")
        
        # Prepare secret data with length header
        data_length = len(secret_data)
        if data_length > max_bytes - 4:
            raise ValueError(f"Secret data too large. Max: {max_bytes-4} bytes")
        
        # Add length header (4 bytes)
        length_bytes = data_length.to_bytes(4, byteorder='big')
        full_data = length_bytes + secret_data
        
        # Convert to binary string
        binary_data = ''.join([format(byte, '08b') for byte in full_data])
        data_index = 0
        
        # Create a copy of pixels
        stego_pixels = pixels.copy()
        
        # Generate embedding sequence
        if self.mode == 'random':
            positions = self._generate_random_positions(height, width, channels, len(binary_data))
        elif self.mode == 'adaptive':
            positions = self._generate_adaptive_positions(pixels, len(binary_data))
        else:  # sequential
            positions = self._generate_sequential_positions(height, width, channels, len(binary_data))
        
        # Embed data
        for pos in positions:
            if data_index >= len(binary_data):
                break
            
            y, x, c = pos
            pixel_value = int(stego_pixels[y, x, c])
            bit = int(binary_data[data_index])
            
            # LSB Matching: +1 or -1 instead of replacement
            lsb = pixel_value & 1
            if lsb != bit:
                if pixel_value == 255:
                    stego_pixels[y, x, c] = 254
                elif pixel_value == 0:
                    stego_pixels[y, x, c] = 1
                else:
                    # Randomly choose +1 or -1
                    stego_pixels[y, x, c] = pixel_value + random.choice([-1, 1])
            
            data_index += 1
        
        # Save stego image
        if output_path is None:
            output_path = cover_path.parent / f"{cover_path.stem}_stego{cover_path.suffix}"
        
        stego_image = Image.fromarray(stego_pixels.astype('uint8'), 'RGB')
        stego_image.save(output_path, quality=100)
        
        logger.info(f"Embedded {data_length} bytes into {output_path}")
        return str(output_path)
    
    @log_operation("LSB Extract")
    def extract(self, stego_path):
        """
        ดึงข้อมูลออกจากภาพ
        
        Args:
            stego_path: path ของภาพที่มีข้อมูลซ่อนอยู่
        
        Returns:
            bytes: ข้อมูลที่ดึงออกมา
        """
        # Load image
        stego_path = Path(stego_path)
        image = Image.open(stego_path)
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        pixels = np.array(image)
        height, width, channels = pixels.shape
        
        # Generate extraction sequence (must match embedding)
        # First, extract length (4 bytes = 32 bits)
        length_positions = self._generate_sequential_positions(height, width, channels, 32)
        
        length_bits = ''
        for pos in length_positions:
            y, x, c = pos
            pixel_value = int(pixels[y, x, c])
            length_bits += str(pixel_value & 1)
        
        # Convert to data length
        data_length = int(length_bits, 2)
        logger.debug(f"Extracting {data_length} bytes")
        
        if data_length <= 0 or data_length > 10000000:  # 10MB sanity check
            raise ValueError(f"Invalid data length: {data_length}")
        
        # Generate positions for actual data
        total_bits = 32 + (data_length * 8)
        if self.mode == 'random':
            positions = self._generate_random_positions(height, width, channels, total_bits)
        elif self.mode == 'adaptive':
            positions = self._generate_adaptive_positions(pixels, total_bits)
        else:
            positions = self._generate_sequential_positions(height, width, channels, total_bits)
        
        # Extract data bits (skip first 32 bits which is length)
        binary_data = ''
        for i, pos in enumerate(positions):
            if i < 32:  # Skip length header
                continue
            if len(binary_data) >= data_length * 8:
                break
            
            y, x, c = pos
            pixel_value = int(pixels[y, x, c])
            binary_data += str(pixel_value & 1)
        
        # Convert binary to bytes
        secret_data = bytearray()
        for i in range(0, len(binary_data), 8):
            byte = binary_data[i:i+8]
            if len(byte) == 8:
                secret_data.append(int(byte, 2))
        
        logger.info(f"Extracted {len(secret_data)} bytes")
        return bytes(secret_data)
    
    def _generate_sequential_positions(self, height, width, channels, num_bits):
        """สร้างลำดับตำแหน่งแบบเรียงตามลำดับ"""
        positions = []
        for i in range(num_bits):
            pixel_index = i // channels
            channel = i % channels
            y = pixel_index // width
            x = pixel_index % width
            if y < height:
                positions.append((y, x, channel))
        return positions
    
    def _generate_random_positions(self, height, width, channels, num_bits):
        """สร้างลำดับตำแหน่งแบบสุ่ม"""
        random.seed(42)  # Fixed seed for reproducibility
        
        all_positions = []
        for y in range(height):
            for x in range(width):
                for c in range(channels):
                    all_positions.append((y, x, c))
        
        random.shuffle(all_positions)
        return all_positions[:num_bits]
    
    def _generate_adaptive_positions(self, pixels, num_bits):
        """สร้างลำดับตำแหน่งแบบ adaptive (เลือกพื้นที่ซับซ้อน)"""
        height, width, channels = pixels.shape
        
        # Calculate edge strength using simple gradient
        gray = np.mean(pixels, axis=2)
        gy, gx = np.gradient(gray)
        edge_strength = np.sqrt(gx**2 + gy**2)
        
        # Create priority map
        positions = []
        for y in range(height):
            for x in range(width):
                for c in range(channels):
                    strength = edge_strength[y, x]
                    positions.append((strength, y, x, c))
        
        # Sort by edge strength (descending)
        positions.sort(reverse=True)
        
        # Return positions with highest edge strength
        return [(y, x, c) for _, y, x, c in positions[:num_bits]]
    
    def calculate_capacity(self, image_path):
        """
        คำนวณความจุของภาพ
        
        Args:
            image_path: path ของภาพ
        
        Returns:
            int: ความจุเป็น bytes
        """
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        width, height = image.size
        channels = 3
        capacity = (height * width * channels * self.bits_per_channel) // 8 - 4  # -4 for length header
        
        return capacity
    
    def blind_extract(self, stego_path, max_bytes=1000):
        """
        พยายามดึงข้อมูลโดยไม่รู้พารามิเตอร์
        (สำหรับ Sequential LSB เท่านั้น)
        
        Args:
            stego_path: path ของภาพ
            max_bytes: จำนวน bytes สูงสุดที่จะพยายามดึง
        
        Returns:
            bytes: ข้อมูลที่ดึงได้
        """
        logger.info("Attempting blind extraction (sequential LSB)")
        
        image = Image.open(stego_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        pixels = np.array(image)
        height, width, channels = pixels.shape
        
        # Try to extract sequentially
        binary_data = ''
        for y in range(height):
            for x in range(width):
                for c in range(channels):
                    pixel_value = int(pixels[y, x, c])
                    binary_data += str(pixel_value & 1)
                    
                    if len(binary_data) >= max_bytes * 8:
                        break
                if len(binary_data) >= max_bytes * 8:
                    break
            if len(binary_data) >= max_bytes * 8:
                break
        
        # Convert to bytes
        extracted = bytearray()
        for i in range(0, len(binary_data), 8):
            byte = binary_data[i:i+8]
            if len(byte) == 8:
                extracted.append(int(byte, 2))
        
        logger.info(f"Blind extracted {len(extracted)} bytes")
        return bytes(extracted)