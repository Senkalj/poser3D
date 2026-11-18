# ScreenGrab

Small Windows app that captures **the monitor its own window is on** — as a PNG screenshot or an MP4 video.
With several monitors, drag the ScreenGrab window onto the one you want, then click.

## Setup (once)
1. Install Python 3.9+ from python.org (tick *Add Python to PATH*; Tkinter is included).
2. In this folder run:
   ```
   pip install -r requirements.txt
   ```

## Run
```
python screengrab.py
```
(or `pythonw screengrab.py` to start without a console window)

- **📷 Screenshot (PNG)** – saves `screenshot_<date_time>.png`.
- **⏺ Record (MP4)** – starts recording that monitor; click **⏹ Stop recording** to save `recording_<date_time>.mp4` (H.264, plays in any player).

**The ScreenGrab window never appears in the image or video.**
- On Windows 10 version 2004 or newer, the window stays on screen but Windows leaves it out of captures
  (`SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE`). The app says *"This window is invisible in captures."*
- On older Windows, the window hides itself instead: briefly for a screenshot, and minimised for a whole
  recording. To stop that recording, click ScreenGrab on the taskbar.
- **Save to** – output folder (default `Pictures\ScreenGrab`). **Open** shows it in Explorer.

## Notes
- The monitor is chosen when you click; moving the window while recording doesn't switch monitors.
- No audio, and the mouse cursor is not captured.
- If the status says the PC couldn't keep up, pick a lower FPS (large/4K monitors at 60 FPS are demanding).
