"""
Image Extractor Utility
Extracts embedded images from XLSX files and prepares them for AI vision analysis.
"""

import base64
import io
from typing import Dict, List, Optional, Tuple
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Extracts and processes images from Excel files."""

    def __init__(self):
        self.max_image_size = (1024, 1024)  # Max dimensions for vision API

    def extract_images_from_xlsx(self, file_path: str) -> Dict[int, List[Dict]]:
        """
        Extract all embedded images from XLSX file and map them to row numbers.

        Args:
            file_path: Path to the XLSX file

        Returns:
            Dictionary mapping row indices to lists of image data:
            {
                row_index: [
                    {
                        'base64': 'base64_encoded_string',
                        'format': 'png/jpeg',
                        'width': int,
                        'height': int
                    },
                    ...
                ]
            }
        """
        images_by_row = {}

        try:
            workbook = load_workbook(file_path, data_only=False)
            sheet = workbook.active

            # Check if there are any images in the worksheet
            if not hasattr(sheet, '_images') or not sheet._images:
                logger.info(f"No embedded images found in {file_path}")
                return images_by_row

            logger.info(f"Found {len(sheet._images)} images in worksheet")

            # Process each image
            for idx, image in enumerate(sheet._images):
                try:
                    row_index = self._get_image_row(image, sheet)

                    if row_index is not None:
                        # Convert image to base64
                        image_data = self._process_image(image, idx)

                        if image_data:
                            if row_index not in images_by_row:
                                images_by_row[row_index] = []
                            images_by_row[row_index].append(image_data)
                            logger.info(f"Extracted image {idx + 1} for row {row_index}")

                except Exception as e:
                    logger.warning(f"Failed to process image {idx + 1}: {str(e)}")
                    continue

            logger.info(f"Successfully extracted images for {len(images_by_row)} rows")

        except Exception as e:
            logger.error(f"Failed to extract images from XLSX: {str(e)}")
            return {}

        return images_by_row

    def _get_image_row(self, image: OpenpyxlImage, sheet) -> Optional[int]:
        """
        Determine which row an image belongs to based on its anchor position.

        Args:
            image: openpyxl Image object
            sheet: Worksheet object

        Returns:
            Row index (0-based) or None if cannot determine
        """
        try:
            # Get the anchor information
            if hasattr(image, 'anchor') and image.anchor:
                anchor = image.anchor

                # For TwoCellAnchor (most common)
                if hasattr(anchor, '_from'):
                    row = anchor._from.row
                    # Convert to 0-based index (subtract 1 for header, another 1 for 0-indexing)
                    # Assuming row 1 is header, data starts at row 2
                    return row - 2 if row >= 2 else 0

                # For OneCellAnchor
                elif hasattr(anchor, 'row'):
                    row = anchor.row
                    return row - 2 if row >= 2 else 0

            logger.warning("Could not determine image row from anchor")
            return None

        except Exception as e:
            logger.warning(f"Error determining image row: {str(e)}")
            return None

    def _process_image(self, image: OpenpyxlImage, image_idx: int) -> Optional[Dict]:
        """
        Process an image: resize if needed and convert to base64.

        Args:
            image: openpyxl Image object
            image_idx: Index of the image for logging

        Returns:
            Dictionary with image data or None if processing fails
        """
        try:
            # Get image data
            image_data = image._data()

            # Open image with PIL
            pil_image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary (remove alpha channel)
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                rgb_image.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = rgb_image

            # Resize if too large
            original_size = pil_image.size
            if pil_image.size[0] > self.max_image_size[0] or pil_image.size[1] > self.max_image_size[1]:
                pil_image.thumbnail(self.max_image_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized image {image_idx + 1} from {original_size} to {pil_image.size}")

            # Convert to base64
            buffered = io.BytesIO()
            image_format = 'JPEG' if pil_image.mode == 'RGB' else 'PNG'
            pil_image.save(buffered, format=image_format, quality=85)
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            return {
                'base64': img_base64,
                'format': image_format.lower(),
                'width': pil_image.size[0],
                'height': pil_image.size[1]
            }

        except Exception as e:
            logger.error(f"Failed to process image {image_idx + 1}: {str(e)}")
            return None

    def extract_from_bytes(self, file_bytes: bytes, filename: str) -> Dict[int, List[Dict]]:
        """
        Extract images from XLSX file bytes (useful for uploaded files).

        Args:
            file_bytes: File content as bytes
            filename: Original filename (for logging)

        Returns:
            Dictionary mapping row indices to image data
        """
        try:
            # Save bytes to temporary location
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name

            # Extract images
            result = self.extract_images_from_xlsx(tmp_path)

            # Clean up
            os.unlink(tmp_path)

            return result

        except Exception as e:
            logger.error(f"Failed to extract images from bytes: {str(e)}")
            return {}


def extract_images_from_file(file_path: str) -> Dict[int, List[Dict]]:
    """
    Convenience function to extract images from an XLSX file.

    Args:
        file_path: Path to the XLSX file

    Returns:
        Dictionary mapping row indices to lists of image data
    """
    extractor = ImageExtractor()
    return extractor.extract_images_from_xlsx(file_path)
