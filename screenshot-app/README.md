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

- **📷 Screenshot (PNG)** – saves `screenshot_<date_time>.png`. The window hides itself for a moment so it isn't in the picture (untick the option to keep it).
- **⏺ Record (MP4)** – starts recording that monitor; click **⏹ Stop recording** to save `recording_<date_time>.mp4` (H.264, plays in any player).
- **Save to** – output folder (default `Pictures\ScreenGrab`). **Open** shows it in Explorer.

## Notes
- The monitor is chosen when you click; moving the window while recording doesn't switch monitors.
- The ScreenGrab window itself appears in videos (it has to stay visible for the Stop button).
- No audio, and the mouse cursor is not captured.
- If the status says the PC couldn't keep up, pick a lower FPS (large/4K monitors at 60 FPS are demanding).
