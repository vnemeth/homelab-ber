"""Streams FM and DAB+ radio from an RTL-SDR dongle over HTTP, as MP3.

GET /<MHz>, e.g. /95.8, streams that FM station until the client disconnects.
GET /<block>?name=<station>, e.g. /5C?name=Radio%20BOB!, streams that DAB+ station
from that block. The name is matched against the station names the block
broadcasts, ignoring case, spaces and punctuation.
?name= also names the stream, in its ID3 title and icy-name header, which players
show instead of the URL.
There is one dongle, so one station plays at a time: clients asking for the
playing station share it, and asking for another one retunes, which ends the
others' streams.

FM runs rtl_fm into lame. DAB+ runs welle-cli, which receives a whole block and
streams its stations as MP3 from its own web server; it stays running while DAB+
stations play, and switches blocks without restarting.

Starting and stopping the dongle in quick succession can hang it until it's
unplugged, and players connect several times in a row when they start a stream
(to probe it, then to play it). So the station keeps playing for LINGER seconds
after the last client is gone, and the dongle rests SETTLE seconds after it was
released before it starts again.

Retuning ends the other station's stream, and its player then reconnects, which
would retune straight back. So for RETIRE seconds after a retune, the previous
station is refused.
"""

import json
import os
import queue
import re
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

PORT = int(os.environ.get("PORT", "8099"))
# Frequency correction of the dongle in ppm
PPM = os.environ.get("PPM", "0")
# FM tuner gain in dB; empty for automatic gain
GAIN = os.environ.get("GAIN", "")
BITRATE = os.environ.get("BITRATE", "128")
# welle-cli's web server, inside the container only
WELLE_PORT = 7979
# How long a DAB+ block may take to list the station asked for
DAB_TIMEOUT = 60
LINGER = 15
SETTLE = 2
RETIRE = 10


def id3_tag(title):
    """An ID3v2.3 tag holding only a title, in UTF-16."""
    text = b"\x01" + title.encode("utf-16")
    frame = b"TIT2" + len(text).to_bytes(4, "big") + b"\x00\x00" + text
    # The tag's size is in 4 bytes of 7 bits each
    size = bytes((len(frame) >> shift) & 0x7F for shift in (21, 14, 7, 0))
    return b"ID3\x03\x00\x00" + size + frame


def normalize(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


class Welle:
    """welle-cli, receiving one DAB+ block."""

    def __init__(self, block):
        self.block = block
        self.proc = subprocess.Popen(
            ["welle-cli", "-c", block, "-w", str(WELLE_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def request(self, path, data=None):
        url = f"http://127.0.0.1:{WELLE_PORT}{path}"
        with urllib.request.urlopen(url, data=data, timeout=5) as response:
            return response.read()

    def running(self):
        return self.proc.poll() is None

    def switch(self, block):
        if block != self.block:
            self.request("/channel", block.encode())
            self.block = block

    def find(self, name):
        """The service ID of the station called name, or None if the block
        doesn't list it within DAB_TIMEOUT."""
        wanted = normalize(name)
        deadline = time.monotonic() + DAB_TIMEOUT
        while time.monotonic() < deadline and self.running():
            try:
                mux = json.loads(self.request("/mux.json"))
            except (OSError, ValueError):
                mux = {}  # still starting, or retuning
            for service in mux.get("services", []):
                if normalize(service["label"]["label"]) == wanted:
                    return service["sid"]
            time.sleep(1)
        return None

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class Tuner:
    """One station's MP3 audio, and the clients reading it."""

    def __init__(self, key, name):
        self.key = key
        self.clients = set()
        # Its own lock, so stopping it under the global one doesn't block fan_out
        self.lock = threading.Lock()
        self.ended = False
        # Sent first to every client, as the stream itself has no title
        self.id3 = id3_tag(name)

    def start(self, audio):
        threading.Thread(target=self.fan_out, args=[audio], daemon=True).start()

    def fan_out(self, audio):
        try:
            while chunk := audio.read(4096):
                with self.lock:
                    for client in self.clients:
                        try:
                            client.put_nowait(chunk)
                        except queue.Full:
                            pass  # a client that can't keep up loses audio
        except OSError:
            pass  # the stream was cut off
        self.end()

    def end(self):
        # The audio ended (stopped, or the receiver failed): tell the clients
        with self.lock:
            self.ended = True
            for client in self.clients:
                client.put(None)


class FmTuner(Tuner):
    """rtl_fm piped into lame."""

    def __init__(self, mhz, name):
        super().__init__(mhz, name)
        self.rtl_fm = subprocess.Popen(
            ["rtl_fm", "-M", "wbfm", "-f", f"{mhz}M", "-r", "48000", "-p", PPM]
            + (["-g", GAIN] if GAIN else [])
            + ["-"],
            stdout=subprocess.PIPE,
        )
        self.lame = subprocess.Popen(
            ["lame", "--quiet", "-r", "-s", "48", "--bitwidth", "16", "--signed",
             "--little-endian", "-m", "m", "-b", BITRATE, "-", "-"],
            stdin=self.rtl_fm.stdout,
            stdout=subprocess.PIPE,
        )
        self.rtl_fm.stdout.close()
        self.start(self.lame.stdout)

    def stop(self):
        # SIGTERM lets rtl_fm release the dongle cleanly; lame then sees the end of
        # its input
        self.rtl_fm.terminate()
        for proc in (self.rtl_fm, self.lame):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


class DabTuner(Tuner):
    """A station's stream from welle-cli's web server."""

    def __init__(self, welle, block, name):
        super().__init__((block, normalize(name)), name)
        self.sock = None
        deadline = time.monotonic() + DAB_TIMEOUT
        sid = welle.find(name)
        # welle-cli lists a station before it knows where its audio is in the
        # block, and answers 503 until then
        while sid and time.monotonic() < deadline:
            if audio := self.connect(sid):
                self.start(audio)
                return
            time.sleep(1)
        print(f"{name} not found in block {block}", flush=True)
        self.end()

    def connect(self, sid):
        """welle-cli's MP3 stream of the station, or None if it isn't ready."""
        try:
            # A plain socket rather than urllib, so stop() can cut off a read that
            # is waiting for audio
            self.sock = socket.create_connection(("127.0.0.1", WELLE_PORT), timeout=10)
            self.sock.sendall(f"GET /mp3/{quote(sid)} HTTP/1.0\r\n\r\n".encode())
            audio = self.sock.makefile("rb")
            ok = b" 200 " in audio.readline()
            # Skip the response headers
            while audio.readline() not in (b"\r\n", b"\n", b""):
                pass
            if ok:
                self.sock.settimeout(30)
                return audio
        except OSError:
            pass
        self.stop()
        self.sock = None
        return None

    def stop(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()


lock = threading.Lock()
tuner = None
welle = None
# When the dongle was last released
released_at = 0.0
linger_timer = None
# Station retuned away from, and until when it is refused
retired = (None, 0.0)


def settle():
    time.sleep(max(0, released_at + SETTLE - time.monotonic()))


def stop_tuner():
    global tuner, released_at
    tuner.stop()
    if isinstance(tuner, FmTuner):
        released_at = time.monotonic()
    tuner = None


def stop_welle():
    global welle, released_at
    if welle:
        welle.stop()
        welle = None
        released_at = time.monotonic()


def start_tuner(station, name):
    """station is MHz for FM, or the block for DAB+."""
    global welle
    if isinstance(station, float):
        stop_welle()
        settle()
        return FmTuner(station, name)
    if welle and welle.running():
        try:
            welle.switch(station)
        except OSError:
            stop_welle()
    if not (welle and welle.running()):
        stop_welle()
        settle()
        welle = Welle(station)
    return DabTuner(welle, station, name)


def station_key(station, name):
    return station if isinstance(station, float) else (station, normalize(name))


def is_retired(key):
    return retired[0] == key and time.monotonic() < retired[1]


def attach(station, name):
    """Returns the tuner and a queue of its audio, or None if the station is
    refused."""
    global tuner, linger_timer, retired
    key = station_key(station, name)
    with lock:
        if is_retired(key):
            return None
        if linger_timer:
            linger_timer.cancel()
            linger_timer = None
        if tuner and (tuner.key != key or tuner.ended):
            if tuner.key != key:
                retired = (tuner.key, time.monotonic() + RETIRE)
            stop_tuner()
        if not tuner:
            tuner = start_tuner(station, name)
        client = queue.Queue(maxsize=256)
        with tuner.lock:
            tuner.clients.add(client)
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
            stop_welle()
            linger_timer = None


class Handler(BaseHTTPRequestHandler):
    def parse_request_path(self):
        """Returns (MHz or block, name), or None after answering a bad path with
        404."""
        url = urlsplit(self.path)
        path = url.path.strip("/").upper()
        name = parse_qs(url.query).get("name", [""])[0][:100]
        # Band III blocks: 5A to 12D, and 13A to 13F
        if re.fullmatch(r"([5-9]|1[0-2])[A-D]|13[A-F]", path):
            if name:
                return path, name
        else:
            try:
                mhz = float(path)
            except ValueError:
                mhz = 0
            if 87.5 <= mhz <= 108:
                return mhz, name or f"FM {mhz}"
        self.send_error(404, "Use /<MHz>, 87.5 to 108, e.g. /95.8, or "
                             "/<DAB+ block>?name=<station>, e.g. /5C?name=Radio%20BOB!")
        return None

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
        station, name = parsed
        if is_retired(station_key(station, name)):
            self.send_error(503, "Just retuned away from this station")
            return
        # The headers go out before tuning: a DAB+ station can take 20 seconds to
        # start, and players give up waiting for headers sooner (Music Assistant
        # after 5 seconds)
        self.send_stream_headers(name)
        if not (attached := attach(station, name)):
            return  # retired in the meantime: the stream ends empty
        this, client = attached
        self.log_message("playing %s %s", station, name)
        try:
            while chunk := client.get():
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            detach(this, client)
            self.log_message("stopped %s %s", station, name)


ThreadingHTTPServer(("", PORT), Handler).serve_forever()
