# Test Videos Directory

Place your test videos here for development and testing.

## Supported Formats
- `.mp4`
- `.avi`
- `.mov`
- `.mkv`
- `.webm`

## Video Analysis Configuration
- Frame sampling interval: `VIDEO_FRAME_INTERVAL` seconds (default: 5)
- Maximum frames analyzed: `VIDEO_MAX_FRAMES` (default: 20)
- Frames are extracted using OpenCV and analyzed as a sequence

## Recommended Test Videos
For development, consider using:

1. **Openly licensed disaster footage** from government agencies
2. **Creative Commons licensed videos** from platforms like Pexels, Pixabay
3. **Your own recordings** (with appropriate permissions)
4. **Synthetic/test videos** you create for specific scenarios

## Example Usage
```python
from ai.services.video_analyzer import analyze_video

result = analyze_video("data/test_videos/flood_drone.mp4")
print(result.summary)
```

## Performance Notes
- Video analysis extracts frames to a temporary directory
- Temporary frames are cleaned up after analysis
- For a 60-second video with 5s interval: ~12 frames analyzed
- Each frame analysis takes ~2-5 seconds depending on hardware
- Total video analysis time: ~30-60 seconds typical

## Note
- Do not commit copyrighted videos to the repository
- Large video files should be added to .gitignore