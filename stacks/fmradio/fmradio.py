"""Streams FM radio from an RTL-SDR dongle over HTTP, as MP3.

GET /<MHz>, e.g. /95.8, streams that station until the client disconnects.
?name=radioeins names it, in the stream's ID3 title and icy-name header, which
players show instead of the URL.
There is one dongle, so one station plays at a time: clients asking for the
playing station share it, and asking for another one retunes, which ends the
others' streams.

Starting and stopping rtl_fm in quick succession can hang the dongle until
it's unplugged, and players connect several times in a row when they start a
stream (to probe it, then to play it). So the tuner keeps running for LINGER
seconds after the last client is gone, and waits SETTLE seconds after it
stopped before it starts again.

Retuning ends the other station's stream, and its player then reconnects,
which would retune straight back. So for RETIRE seconds after a retune, the
previous station is refused.
"""

import os
import queue
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PORT = int(os.environ.get("PORT", "8099"))
# Frequency correction of the dongle in ppm
PPM = os.environ.get("PPM", "0")
# Tuner gain in dB; empty for automatic gain
GAIN = os.environ.get("GAIN", "")
BITRATE = os.environ.get("BITRATE", "128k")
LINGER = 15
SETTLE = 2
RETIRE = 10


class Tuner:
    """The running rtl_fm | ffmpeg pipeline, and the clients reading from it."""

    def __init__(self, mhz, name):
        self.mhz = mhz
        self.clients = set()
        # Its own lock, so stopping it under the global one doesn't block fan_out
        self.lock = threading.Lock()
        self.ended = False
        # The stream's ID3 tag, which comes first, for clients that join later
        self.id3 = b""
        self.rtl_fm = subprocess.Popen(
            ["rtl_fm", "-M", "wbfm", "-f", f"{mhz}M", "-r", "48000", "-p", PPM]
            + (["-g", GAIN] if GAIN else [])
            + ["-"],
            stdout=subprocess.PIPE,
        )
        self.ffmpeg = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", "48000", "-ac", "1",
             "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", BITRATE,
             "-metadata", f"title={name}", "-f", "mp3", "pipe:1"],
            stdin=self.rtl_fm.stdout,
            stdout=subprocess.PIPE,
        )
        self.rtl_fm.stdout.close()
        threading.Thread(target=self.fan_out, daemon=True).start()

    def fan_out(self):
        header = self.ffmpeg.stdout.read(10)
        if header[:3] == b"ID3":
            # The tag's size is in 4 bytes of 7 bits each, after its 10-byte header
            size = 0
            for byte in header[6:10]:
                size = size << 7 | byte
            id3 = header + self.ffmpeg.stdout.read(size)
        else:
            id3 = header
        # Under the lock, so a client joining now gets it exactly once
        with self.lock:
            self.id3 = id3
            for client in self.clients:
                client.put(self.id3)
        while chunk := self.ffmpeg.stdout.read(4096):
            with self.lock:
                for client in self.clients:
                    try:
                        client.put_nowait(chunk)
                    except queue.Full:
                        pass  # a client that can't keep up loses audio
        # The pipeline ended (stopped, or rtl_fm failed): tell the clients
        with self.lock:
            self.ended = True
            for client in self.clients:
                client.put(None)

    def stop(self):
        # SIGTERM lets rtl_fm release the dongle cleanly; ffmpeg then sees the end
        # of its input
        self.rtl_fm.terminate()
        for proc in (self.rtl_fm, self.ffmpeg):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


lock = threading.Lock()
tuner = None
stopped_at = 0.0
linger_timer = None
# Station retuned away from, and until when it is refused
retired = (None, 0.0)


def stop_tuner():
    global tuner, stopped_at
    tuner.stop()
    tuner = None
    stopped_at = time.monotonic()


def attach(mhz, name):
    """Returns the tuner and a queue of its audio, or None if mhz is refused."""
    global tuner, linger_timer, retired
    with lock:
        if retired[0] == mhz and time.monotonic() < retired[1]:
            return None
        if linger_timer:
            linger_timer.cancel()
            linger_timer = None
        if tuner and (tuner.mhz != mhz or tuner.ended):
            if tuner.mhz != mhz:
                retired = (tuner.mhz, time.monotonic() + RETIRE)
            stop_tuner()
        if not tuner:
            time.sleep(max(0, stopped_at + SETTLE - time.monotonic()))
            tuner = Tuner(mhz, name)
        client = queue.Queue(maxsize=256)
        with tuner.lock:
            tuner.clients.add(client)
            if tuner.id3:
                client.put(tuner.id3)
            if tuner.ended:
                client.put(None)
        return tuner, client


def detach(this, client):
    global linger_timer
    with lock:
        with this.lock:
            this.clients.discard(client)
        if this is tuner and not this.clients:
            linger_timer = threading.Timer(LINGER, linger_expired, [this])
            linger_timer.start()


def linger_expired(this):
    global linger_timer
    with lock:
        if this is tuner and not this.clients:
            stop_tuner()
            linger_timer = None


class Handler(BaseHTTPRequestHandler):
    def parse_request_path(self):
        """Returns (MHz, name), or None after answering a bad path with 404."""
        url = urlsplit(self.path)
        try:
            mhz = float(url.path.strip("/"))
        except ValueError:
            mhz = 0
        if not 87.5 <= mhz <= 108:
            self.send_error(404, "Use /<MHz>, 87.5 to 108, e.g. /95.8")
            return None
        name = parse_qs(url.query).get("name", [f"FM {mhz}"])[0][:100]
        return mhz, name

    def send_stream_headers(self, name):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        # Headers are Latin-1
        self.send_header("icy-name", name.encode("latin-1", "replace").decode("latin-1"))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def do_HEAD(self):
        if parsed := self.parse_request_path():
            self.send_stream_headers(parsed[1])

    def do_GET(self):
        if not (parsed := self.parse_request_path()):
            return
        mhz, name = parsed
        attached = attach(mhz, name)
        if not attached:
            self.send_error(503, "Just retuned away from this station")
            return
        this, client = attached
        self.log_message("playing %s MHz", mhz)
        self.send_stream_headers(name)
        try:
            while chunk := client.get():
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            detach(this, client)
            self.log_message("stopped %s MHz", mhz)


ThreadingHTTPServer(("", PORT), Handler).serve_forever()
