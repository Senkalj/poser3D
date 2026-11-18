"""ScreenGrab - capture the monitor this window is on, as a PNG or an MP4.

Run:  python screengrab.py
Needs: pip install -r requirements.txt   (mss, imageio-ffmpeg)
"""

import ctypes
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mss
import mss.tools
import imageio_ffmpeg

# mss 10+ renamed mss.mss() to mss.MSS(); support both.
MSS = getattr(mss, "MSS", None) or mss.mss


def enable_dpi_awareness():
    """On Windows, make Tk report real pixel coordinates (same as mss uses).

    Without this, with display scaling at e.g. 150%, Tk's window position
    would be in scaled units and we could pick the wrong monitor.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def exclude_from_capture(root):
    """Keep the window visible on screen but leave it out of captures.

    Uses SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE), available on
    Windows 10 version 2004 and newer. Returns True if it worked.
    """
    if sys.platform != "win32":
        return False
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        root.update()  # make sure the real top-level window exists
        hwnd = user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
        return bool(user32.SetWindowDisplayAffinity(hwnd, 0x11))  # WDA_EXCLUDEFROMCAPTURE
    except Exception:
        return False


def monitor_for_rect(monitors, x, y, w, h):
    """Return the monitor (mss dict) that overlaps the given rectangle most."""
    best, best_area = None, -1
    for mon in monitors:
        ox = max(0, min(x + w, mon["left"] + mon["width"]) - max(x, mon["left"]))
        oy = max(0, min(y + h, mon["top"] + mon["height"]) - max(y, mon["top"]))
        if ox * oy > best_area:
            best, best_area = mon, ox * oy
    return best


def timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class Recorder(threading.Thread):
    """Grabs frames of one monitor and pipes them to ffmpeg (H.264 MP4)."""

    def __init__(self, monitor, path, fps, on_done):
        super().__init__(daemon=True)
        # H.264 (yuv420p) needs even width/height.
        self.monitor = dict(monitor)
        self.monitor["width"] -= self.monitor["width"] % 2
        self.monitor["height"] -= self.monitor["height"] % 2
        self.path = path
        self.fps = fps
        self.on_done = on_done
        self.stop_event = threading.Event()
        self.frames = 0
        self.dropped = 0

    def run(self):
        error = None
        size = (self.monitor["width"], self.monitor["height"])
        writer = imageio_ffmpeg.write_frames(
            str(self.path),
            size,
            fps=self.fps,
            codec="libx264",
            pix_fmt_in="rgb24",
            pix_fmt_out="yuv420p",
            macro_block_size=1,
            output_params=["-preset", "veryfast", "-crf", "23"],
        )
        try:
            writer.send(None)  # start ffmpeg
            with MSS() as sct:  # mss objects must be created in this thread
                start = time.perf_counter()
                frame = None
                while not self.stop_event.is_set():
                    frame = sct.grab(self.monitor).rgb
                    # Keep video length equal to real time: if capturing fell
                    # behind, repeat the frame to fill the gap.
                    due = int((time.perf_counter() - start) * self.fps) + 1
                    repeats = max(1, due - self.frames)
                    self.dropped += repeats - 1
                    for _ in range(repeats):
                        writer.send(frame)
                    self.frames += repeats
                    wait = start + self.frames / self.fps - time.perf_counter()
                    if wait > 0:
                        self.stop_event.wait(wait)
        except Exception as exc:  # report to the UI instead of dying silently
            error = exc
        finally:
            try:
                writer.close()
            except Exception as exc:
                error = error or exc
        self.on_done(self, error)


class App:
    def __init__(self, root):
        self.root = root
        self.recorder = None
        self.rec_started = 0.0

        root.title("ScreenGrab")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        self.out_dir = tk.StringVar(value=str(Path.home() / "Pictures" / "ScreenGrab"))
        self.fps = tk.IntVar(value=30)
        self.status = tk.StringVar(value="Ready")
        self.restore_stops = False  # fallback mode: restoring the window stops recording

        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(root, padding=8)
        frm.grid()

        self.png_btn = ttk.Button(frm, text="📷  Screenshot (PNG)", command=self.take_png)
        self.png_btn.grid(row=0, column=0, sticky="ew", **pad)
        self.rec_btn = ttk.Button(frm, text="⏺  Record (MP4)", command=self.toggle_record)
        self.rec_btn.grid(row=0, column=1, sticky="ew", **pad)

        self.mode_label = ttk.Label(frm, foreground="#555", wraplength=380)
        self.mode_label.grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        fps_row = ttk.Frame(frm)
        fps_row.grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(fps_row, text="Video FPS:").pack(side="left")
        self.fps_box = ttk.Combobox(fps_row, textvariable=self.fps, values=(10, 15, 24, 30, 60),
                                    width=4, state="readonly")
        self.fps_box.pack(side="left", padx=4)

        dir_row = ttk.Frame(frm)
        dir_row.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(dir_row, text="Save to:").pack(side="left")
        ttk.Entry(dir_row, textvariable=self.out_dir, width=34).pack(side="left", padx=4)
        ttk.Button(dir_row, text="…", width=3, command=self.choose_dir).pack(side="left")
        ttk.Button(dir_row, text="Open", command=self.open_dir).pack(side="left", padx=4)

        ttk.Label(frm, textvariable=self.status, foreground="#555").grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Map>", self._on_map)

        # Preferred: Windows leaves this window out of every capture, so it can
        # stay on screen. Otherwise it gets hidden while capturing.
        self.invisible = exclude_from_capture(root)
        self.mode_label.config(text=(
            "This window is invisible in captures." if self.invisible else
            "This window hides while capturing. To stop a recording, "
            "click ScreenGrab on the taskbar."))

    # ---- helpers -------------------------------------------------------
    def current_monitor(self):
        """The monitor the app window is (mostly) on."""
        self.root.update_idletasks()
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        with MSS() as sct:
            monitors = sct.monitors[1:]  # [0] is the whole virtual desktop
            mon = monitor_for_rect(monitors, x, y, w, h)
            return mon, monitors.index(mon) + 1

    def output_dir(self):
        path = Path(self.out_dir.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_dir.get())
        if d:
            self.out_dir.set(d)

    def open_dir(self):
        path = self.output_dir()
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')

    # ---- screenshot ----------------------------------------------------
    def take_png(self):
        try:
            mon, idx = self.current_monitor()
            path = self.output_dir() / f"screenshot_{timestamp()}.png"
        except Exception as exc:
            messagebox.showerror("ScreenGrab", str(exc))
            return
        if self.invisible:
            self._grab_png(mon, idx, path, restore=False)
        else:
            self.root.withdraw()
            # Give Windows time to finish the hide animation before grabbing.
            self.root.after(300, lambda: self._grab_png(mon, idx, path, restore=True))

    def _grab_png(self, mon, idx, path, restore):
        try:
            with MSS() as sct:
                shot = sct.grab(mon)
                mss.tools.to_png(shot.rgb, shot.size, output=str(path))
            self.status.set(f"Saved {path.name}  (monitor {idx}, {shot.width}×{shot.height})")
        except Exception as exc:
            messagebox.showerror("ScreenGrab", f"Screenshot failed:\n{exc}")
        finally:
            if restore:
                self.root.deiconify()

    # ---- recording -----------------------------------------------------
    def toggle_record(self):
        if self.recorder:
            self.rec_btn.config(state="disabled", text="Saving…")
            self.recorder.stop_event.set()
            return
        try:
            mon, idx = self.current_monitor()
            path = self.output_dir() / f"recording_{timestamp()}.mp4"
        except Exception as exc:
            messagebox.showerror("ScreenGrab", str(exc))
            return
        self.recorder = Recorder(mon, path, int(self.fps.get()),
                                 on_done=lambda r, e: self.root.after(0, self._record_done, r, e))
        self.rec_btn.config(text="⏹  Stop recording")
        self.png_btn.config(state="disabled")
        self.fps_box.config(state="disabled")
        if self.invisible:
            self._start_recorder(idx)
        else:
            # Minimise first and wait for the animation, so no trace is recorded.
            self.root.iconify()
            self.root.after(400, self._start_recorder, idx)

    def _start_recorder(self, idx):
        self.rec_started = time.perf_counter()
        self.recorder.start()
        self.restore_stops = not self.invisible
        self._tick(idx)

    def _on_map(self, event):
        """Fallback mode: the user restored the window from the taskbar -> stop."""
        if event.widget is self.root and self.restore_stops and self.recorder:
            self.restore_stops = False
            self.toggle_record()

    def _tick(self, idx):
        if not self.recorder or self.recorder.stop_event.is_set():
            return
        secs = int(time.perf_counter() - self.rec_started)
        self.status.set(f"● Recording monitor {idx}  {secs // 60:02d}:{secs % 60:02d}")
        self.root.after(500, self._tick, idx)

    def _record_done(self, rec, error):
        self.recorder = None
        self.restore_stops = False
        if self.root.state() == "iconic":
            self.root.deiconify()
        self.rec_btn.config(state="normal", text="⏺  Record (MP4)")
        self.png_btn.config(state="normal")
        self.fps_box.config(state="readonly")
        if error:
            messagebox.showerror("ScreenGrab", f"Recording failed:\n{error}")
            self.status.set("Recording failed")
            return
        msg = f"Saved {rec.path.name}"
        if rec.frames and rec.dropped / rec.frames > 0.2:
            msg += "  (PC couldn't keep up — try a lower FPS)"
        self.status.set(msg)

    def on_close(self):
        if self.recorder and self.recorder.is_alive():
            self.recorder.stop_event.set()
            self.recorder.join(timeout=10)
        self.root.destroy()


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
