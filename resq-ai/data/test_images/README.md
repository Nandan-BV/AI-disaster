# Test Images Directory

Place your test images here for development and testing.

## Supported Formats
- `.jpg`, `.jpeg`
- `.png`
- `.webp`
- `.bmp`

## Recommended Test Images
For development, consider using openly licensed disaster images from:

1. **NASA/FEMA public domain disaster imagery**
2. **Wikimedia Commons disaster photos**
3. **OpenStreetMap disaster imagery**
4. **Your own photos** (with appropriate permissions)

## Example Usage
```python
from ai.services.image_analyzer import analyze_image

result = analyze_image("data/test_images/flood_street.jpg")
print(result.summary)
```

## Note
- Maximum image dimension: 1024px (configurable via MAX_IMAGE_SIZE)
- Images larger than this will be automatically resized
- Do not commit copyrighted images to the repository