# AI-Powered Image Analysis Feature

## Overview

The standardization pipeline now includes **automatic AI-powered image analysis** for RAG 1 format. When processing XLSX files with embedded images, the system will:

1. Extract images from the Excel file
2. Analyze them using Azure OpenAI Vision API
3. Generate intelligent descriptions focused on procedural information
4. Populate the `image_caption` field in RAG 1 records

## Features

### ✨ Key Capabilities

- **Automatic Image Extraction**: Detects and extracts embedded images from XLSX files
- **Multi-Image Support**: Handles multiple images per row, combining descriptions
- **Intelligent Analysis**: Focuses on extracting:
  - Step-by-step instructions
  - Procedural information
  - Flowchart processes
  - Important text content
  - Actionable information
- **Graceful Error Handling**: Falls back to `null` if images can't be analyzed
- **Sequential Processing**: Processes images sequentially for reliability
- **No Performance Impact**: Only runs when images are present in XLSX files

## How It Works

### Pipeline Flow

```
XLSX File → Extract Images → Process Data → Standardize Records →
Analyze Images with Vision AI → Update image_caption → Return Results
```

### Step-by-Step Process

1. **Ingestion** ([src/core/ingestion.py](src/core/ingestion.py)):
   - Reads XLSX file and extracts data
   - Simultaneously extracts embedded images
   - Maps images to their corresponding row indices

2. **Standardization** ([src/core/standardization.py](src/core/standardization.py)):
   - Creates standardized RAG 1 records
   - For each record with images:
     - Sends image(s) to Azure OpenAI Vision API
     - Receives intelligent description
     - Populates `image_caption` field

3. **Vision Analysis** ([src/gpt/client.py](src/gpt/client.py)):
   - Uses specialized prompts for procedural content
   - Handles single or multiple images per row
   - Returns concise, actionable descriptions

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# Azure OpenAI Vision Configuration
# Optional - if not specified, uses AZURE_OPENAI_DEPLOYMENT_NAME
# Recommended: use a vision-capable model like gpt-4o
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o
```

### Prerequisites

1. **Azure OpenAI Vision Model**: Deploy a vision-capable model (e.g., gpt-4o, gpt-4-vision)
2. **Dependencies**: Run `pip install -r requirements.txt` to install:
   - `Pillow==11.1.0` (image processing)
   - `openpyxl==3.1.5` (already included)

## Usage

### Automatic Processing

The feature runs **automatically** when:
- Processing an XLSX file (not CSV)
- Target format is RAG 1
- Images are embedded in the Excel file

No additional parameters needed! The pipeline handles everything.

### Example

#### Input XLSX:
```
| doc_ref | category | header           | body_content      | [Image]        |
|---------|----------|------------------|-------------------|----------------|
| ART001  | Tutorial | Setup Process    | Complete guide... | [embedded IMG] |
```

#### Output RAG 1:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "articulo_id": "ART001",
  "tipo": "Tutorial",
  "numero": 0,
  "titulo": "Setup Process",
  "texto": "Complete guide...",
  "image_caption": "Paso 1: Open settings menu. Paso 2: Navigate to configuration. Paso 3: Click save.",
  "keywords": null,
  "embedding": null
}
```

## Technical Details

### Image Processing

**Extraction** ([src/utils/image_extractor.py](src/utils/image_extractor.py)):
- Extracts images using `openpyxl` library
- Converts images to RGB format (removes alpha channel)
- Resizes large images to max 1024x1024 pixels
- Encodes to base64 for API transmission
- Maps images to row indices based on anchor position

**Analysis Prompts** ([src/gpt/prompts.py](src/gpt/prompts.py)):
- `image_analysis_prompt()`: For single images
- `multiple_images_analysis_prompt()`: For multiple images per row
- Focused on extracting:
  - Sequential steps and procedures
  - Flowchart processes
  - Important text content
  - Actionable information

### Multiple Images per Row

When a row contains multiple images:

```
"Imagen 1: [description of first image]. Imagen 2: [description of second image]."
```

Or for sequential steps:

```
"Paso 1 (Imagen 1): [step description]. Paso 2 (Imagen 2): [step description]."
```

### Error Handling

**Scenarios where `image_caption` = `null`:**
- No images found in XLSX file
- Image extraction fails
- Vision API call fails
- Vision deployment not configured
- Image is corrupted or unreadable

**Logging:**
- All image processing is logged with detailed information
- Warnings for failed extractions
- Errors logged without breaking the pipeline

## Performance Considerations

### Processing Time

- **Image Extraction**: ~0.1-0.5s per XLSX file
- **Vision Analysis**: ~2-5s per image (depends on Azure OpenAI latency)
- **Sequential Processing**: Images processed one at a time for reliability

### Cost Optimization

- Images only processed when present (no cost for CSV files)
- Resized to 1024x1024 max (reduces token usage)
- Only RAG 1 format supported (RAG 2 doesn't have image_caption field)

## Limitations

1. **XLSX Only**: CSV files don't support embedded images
2. **RAG 1 Only**: RAG 2 schema doesn't include `image_caption` field
3. **Sequential Processing**: Images processed one at a time (not in parallel)
4. **Vision Model Required**: Requires Azure OpenAI deployment with vision capability

## Testing Recommendations

### Create Test XLSX Files

1. **Single Image Test**:
   - Create XLSX with data in rows
   - Embed one image per row (Insert → Pictures → Place in Cell)
   - Process through pipeline

2. **Multiple Images Test**:
   - Embed 2-3 images in the same row
   - Verify combined descriptions

3. **No Images Test**:
   - Process XLSX without images
   - Verify `image_caption` is `null`

4. **Mixed Content Test**:
   - Some rows with images, some without
   - Verify correct handling

### Testing Steps

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env
cp .env.example .env
# Edit .env and add your AZURE_OPENAI_VISION_DEPLOYMENT

# 3. Run the server
python main.py

# 4. Test with XLSX file containing images
curl -X POST "http://localhost:8000/standardize" \
  -F "file=@test_with_images.xlsx" \
  -F "target_rag=rag1"
```

## Files Modified

### New Files
- `src/utils/image_extractor.py` - Image extraction utility

### Modified Files
- `requirements.txt` - Added Pillow dependency
- `src/core/ingestion.py` - Extract images during ingestion
- `src/core/standardization.py` - Analyze images and update captions
- `src/core/pipeline.py` - Pass images through pipeline
- `src/gpt/client.py` - Added vision API methods
- `src/gpt/prompts.py` - Added vision prompts
- `.env.example` - Added vision deployment configuration

## Troubleshooting

### "Vision deployment no configurado"
**Solution**: Add `AZURE_OPENAI_VISION_DEPLOYMENT` to your `.env` file

### Images not being detected
**Solution**:
- Verify images are embedded in cells (not floating)
- Check Excel file format is `.xlsx` (not `.xls`)
- Review logs for extraction errors

### Vision API errors
**Solution**:
- Verify your Azure OpenAI deployment supports vision
- Check API key and endpoint configuration
- Ensure sufficient API quota

### image_caption always null
**Solution**:
- Check if XLSX file actually contains images
- Review application logs for errors
- Verify vision deployment is correctly configured

## Future Enhancements

Potential improvements for future versions:

1. **Parallel Processing**: Analyze multiple images concurrently
2. **RAG 2 Support**: Add image analysis for RAG 2 format
3. **Custom Prompts**: Allow users to customize vision prompts
4. **Image Metadata**: Extract image metadata (dimensions, format, etc.)
5. **OCR Enhancement**: Specialized OCR for text-heavy images
6. **Diagram Understanding**: Enhanced analysis for flowcharts and diagrams

## Support

For issues or questions:
- Review application logs (`LOG_LEVEL=DEBUG` for detailed output)
- Check Azure OpenAI service status
- Verify all environment variables are correctly set

---

**Feature Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: 2025-11-14
