# GrowTent Backend v0.403 – Visible HDR enhancement for camera images

- Improve the HDR-like mode in both the analysis ZIP (`camera-hdr.jpg`) and the optional fullscreen camera viewer. The original `camera.jpg` and default preview remain untouched.
- Use an adaptive luminance tone curve from the image histogram rather than the former very subtle shadow/highlight masks; add bounded local-contrast/clarity enhancement and modest colour correction. Preserve the source image resolution up to 16 MP (including 4K) and high-quality JPEG 4:4:4 output.
- The algorithm is still **single-frame image enhancement, not true multi-exposure HDR**. Clipped whites, missing sensor detail, and defocus cannot be recovered. No camera settings, exposure, network routes, ESP controls, or stored history are changed.
- The `camera_snapshot.hdr.method` value identifies the new version: `single_frame_adaptive_tone_mapping_v2`; all other JSON export fields retain their previous structure. JSON-only API remains available.
- Verify improvement against the actual uploaded 1920×1080 tent snapshot: image-channel mean absolute difference versus the original rises from about 2.5/255 (v0.402) to approximately 19/255; the original JPEG is byte-identical.
- Add regression tests for substantial real-frame improvement, monotonic tone mapping on degenerate synthetic frames, high-resolution processing, and failure fallbacks. No database or schema migration.
- Testing: local automated regressions and ZIP integrity; live RTSP camera, Docker and PostgreSQL integration remain unverified.
