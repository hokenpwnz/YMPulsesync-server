import os
import json
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "10000"))

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "").strip()
LASTFM_USERNAME = os.environ.get("LASTFM_USERNAME", "").strip()

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"

CACHE_SECONDS = 5

cached_track = None
cached_status = "stopped"
last_fetch_time = 0

def log(message):
print(message, flush=True)

def fetch_lastfm_track():
global cached_track
global cached_status
global last_fetch_time

```
now = time.time()

if now - last_fetch_time < CACHE_SECONDS:
    return cached_track, cached_status

last_fetch_time = now

if not LASTFM_API_KEY:
    log("ERROR: LASTFM_API_KEY не задан")
    cached_track = None
    cached_status = "error"
    return cached_track, cached_status

if not LASTFM_USERNAME:
    log("ERROR: LASTFM_USERNAME не задан")
    cached_track = None
    cached_status = "error"
    return cached_track, cached_status

params = {
    "method": "user.getrecenttracks",
    "user": LASTFM_USERNAME,
    "api_key": LASTFM_API_KEY,
    "format": "json",
    "limit": "1"
}

url = LASTFM_API_URL + "?" + urllib.parse.urlencode(params)

try:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PulseSync/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=10
    ) as response:
        raw_data = response.read().decode("utf-8")

    data = json.loads(raw_data)

    if "error" in data:
        error_code = data.get("error", "unknown")
        error_message = data.get(
            "message",
            "Unknown Last.fm error"
        )

        log(
            f"Last.fm ERROR {error_code}: "
            f"{error_message}"
        )

        cached_track = None
        cached_status = "error"

        return cached_track, cached_status

    recent_tracks = data.get(
        "recenttracks",
        {}
    )

    tracks = recent_tracks.get(
        "track",
        []
    )

    if not tracks:
        log("Last.fm: recent tracks пуст")

        cached_track = None
        cached_status = "stopped"

        return cached_track, cached_status

    if isinstance(tracks, dict):
        tracks = [tracks]

    lastfm_track = tracks[0]

    attributes = lastfm_track.get(
        "@attr",
        {}
    )

    is_now_playing = (
        attributes.get("nowplaying") == "true"
    )

    artist_data = lastfm_track.get(
        "artist",
        {}
    )

    if isinstance(artist_data, dict):
        artist = (
            artist_data.get("#text", "")
            or artist_data.get("name", "")
        )
    else:
        artist = str(artist_data)

    artist = artist.strip()

    title = str(
        lastfm_track.get(
            "name",
            ""
        )
    ).strip()

    album_data = lastfm_track.get(
        "album",
        {}
    )

    if isinstance(album_data, dict):
        album = album_data.get(
            "#text",
            ""
        )
    else:
        album = str(album_data)

    album = album.strip()

    cover = ""

    images = lastfm_track.get(
        "image",
        []
    )

    if isinstance(images, list):
        preferred_sizes = [
            "extralarge",
            "large",
            "medium",
            "small"
        ]

        for wanted_size in preferred_sizes:
            for image in images:
                if not isinstance(image, dict):
                    continue

                if image.get("size") != wanted_size:
                    continue

                candidate = image.get(
                    "#text",
                    ""
                )

                if candidate:
                    cover = candidate
                    break

            if cover:
                break

    track_url = lastfm_track.get(
        "url",
        ""
    )

    track = {
        "artist": artist,
        "title": title,
        "album": album,
        "album_id": "",
        "track_id": "",
        "cover": cover,
        "url": track_url
    }

    cached_track = track

    if is_now_playing:
        cached_status = "playing"
    else:
        cached_status = "stopped"

    log(
        "LASTFM TRACK: "
        f"{artist} - {title} "
        f"| status: {cached_status} "
        f"| cover: "
        f"{'yes' if cover else 'no'}"
    )

    return cached_track, cached_status

except Exception as error:
    log(
        "Last.fm request ERROR: "
        f"{type(error).__name__}: {error}"
    )

    if cached_track is not None:
        return cached_track, cached_status

    cached_status = "error"

    return None, cached_status
```

class PulseSyncHandler(BaseHTTPRequestHandler):

```
def send_cors_headers(self):
    self.send_header(
        "Access-Control-Allow-Origin",
        "*"
    )

    self.send_header(
        "Access-Control-Allow-Methods",
        "GET, HEAD, OPTIONS"
    )

    self.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type"
    )

def send_json(self, data, status=200):
    body = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")

    self.send_response(status)

    self.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    self.send_header(
        "Content-Length",
        str(len(body))
    )

    self.send_header(
        "Cache-Control",
        "no-store, no-cache, must-revalidate"
    )

    self.send_cors_headers()

    self.end_headers()

    return body

def do_HEAD(self):
    if self.path == "/":
        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.send_cors_headers()

        self.end_headers()

        return

    if self.path == "/track":
        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.send_cors_headers()

        self.end_headers()

        return

    self.send_response(404)
    self.send_cors_headers()
    self.end_headers()

def do_OPTIONS(self):
    self.send_response(204)
    self.send_cors_headers()
    self.end_headers()

def do_GET(self):
    parsed_url = urllib.parse.urlparse(
        self.path
    )

    path = parsed_url.path

    if path == "/":
        body = (
            b"PulseSync Last.fm server is running."
        )

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.send_cors_headers()

        self.end_headers()

        self.wfile.write(body)

        return

    if path == "/track":
        track, status = fetch_lastfm_track()

        response = {
            "track": track,
            "status": status
        }

        body = self.send_json(response)

        self.wfile.write(body)

        return

    body = json.dumps(
        {
            "error": "Not found"
        }
    ).encode("utf-8")

    self.send_response(404)

    self.send_header(
        "Content-Type",
        "application/json"
    )

    self.send_header(
        "Content-Length",
        str(len(body))
    )

    self.send_cors_headers()

    self.end_headers()

    self.wfile.write(body)

def log_message(self, format, *args):
    log(
        "%s - %s"
        % (
            self.address_string(),
            format % args
        )
    )
```

def main():
log("")
log("========================================")
log("PulseSync Last.fm server starting...")
log("========================================")

```
log(f"PORT: {PORT}")

log(
    "LASTFM_API_KEY: "
    + (
        "есть"
        if LASTFM_API_KEY
        else "НЕТ"
    )
)

log(
    "LASTFM_USERNAME: "
    + (
        LASTFM_USERNAME
        if LASTFM_USERNAME
        else "НЕТ"
    )
)

log("")

if not LASTFM_API_KEY:
    log(
        "WARNING: "
        "LASTFM_API_KEY не установлен."
    )

if not LASTFM_USERNAME:
    log(
        "WARNING: "
        "LASTFM_USERNAME не установлен."
    )

server = ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    PulseSyncHandler
)

log(
    f"PulseSync server started on port {PORT}"
)

log(
    "Source: Last.fm user.getrecenttracks"
)

log("")

try:
    server.serve_forever()

except KeyboardInterrupt:
    log("Server stopping...")

finally:
    server.server_close()
```

if **name** == "**main**":
main()
