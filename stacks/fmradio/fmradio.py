"""Streams FM radio from an RTL-SDR dongle over HTTP, as MP3.

GET /<MHz>, e.g. /95.8, tunes to that station and streams it until the client
disconnects. There is one dongle, so a new request takes it over from the
previous one.
"""

import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8099"))
# Frequency correction of the dongle in ppm
PPM = os.environ.get("PPM", "0")
# Tuner gain in dB; empty for automatic gain
GAIN = os.environ.get("GAIN", "")
BITRATE = os.environ.get("BITRATE", "128k")

lock = threading.Lock()
current = None  # (rtl_fm, ffmpeg) of the station that is playing


def stop(pipeline):
    for proc in pipeline:
        proc.terminate()
    for proc in pipeline:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def start(mhz):
    global current
    with lock:
        # Free the dongle before tuning again
        if current:
            stop(current)
        rtl_fm = subprocess.Popen(
            ["rtl_fm", "-M", "wbfm", "-f", f"{mhz}M", "-r", "48000", "-p", PPM]
            + (["-g", GAIN] if GAIN else [])
            + ["-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", "48000", "-ac", "1",
             "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", BITRATE, "-f", "mp3", "pipe:1"],
            stdin=rtl_fm.stdout,
            stdout=subprocess.PIPE,
        )
        rtl_fm.stdout.close()
        current = (rtl_fm, ffmpeg)
        return current


def release(pipeline):
    global current
    with lock:
        if current is pipeline:
            stop(pipeline)
            current = None


class Handler(BaseHTTPRequestHandler):
    def parse_mhz(self):
        try:
            mhz = float(self.path.strip("/"))
        except ValueError:
            mhz = 0
        if not 87.5 <= mhz <= 108:
            self.send_error(404, "Use /<MHz>, 87.5 to 108, e.g. /95.8")
            return None
        return mhz

    def send_stream_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def do_HEAD(self):
        if self.parse_mhz():
            self.send_stream_headers()

    def do_GET(self):
        mhz = self.parse_mhz()
        if not mhz:
            return
        self.log_message("tuning to %s MHz", mhz)
        pipeline = start(mhz)
        self.send_stream_headers()
        try:
            while chunk := pipeline[1].stdout.read(4096):
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            release(pipeline)
            self.log_message("stopped %s MHz", mhz)


ThreadingHTTPServer(("", PORT), Handler).serve_forever()
