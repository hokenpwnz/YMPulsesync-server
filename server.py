import os
import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from yandex_music import Client


PORT = int(os.environ.get("PORT", "10000"))

LASTFM_API_KEY = os.environ.get(
    "LASTFM_API_KEY",
    ""
).strip()

LASTFM_USERNAME = os.environ.get(
    "LASTFM_USERNAME",
    ""
).strip()

YANDEX_TOKEN = os.environ.get(
    "YANDEX_TOKEN",
    ""
).strip()

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"

CACHE_SECONDS = 5

cached_track = None
cached_status = "stopped"
last_fetch_time = 0

yandex_cache = {}

yandex_client = None


def log(message):
    print(message, flush=True)


def get_yandex_client():
    global yandex_client

    if yandex_client is not None:
        return yandex_client

    if not YANDEX_TOKEN:
        log("YANDEX_TOKEN не задан")
        return None

    try:
        log("Инициализация Yandex Music API...")

        yandex_client = Client(
            YANDEX_TOKEN
        ).init()

        log("Yandex Music API: подключён")

        return yandex_client

    except Exception as error:
        log(
            f"Yandex Music init ERROR: "
            f"{type(error).__name__}: {error}"
        )

        yandex_client = None

        return None


def search_yandex_track(artist, title):
    cache_key = (
        f"{artist} - {title}"
        .lower()
        .strip()
    )

    if cache_key in yandex_cache:
        return yandex_cache[cache_key]

    client = get_yandex_client()

    if client is None:
        yandex_cache[cache_key] = None
        return None

    query = f"{artist} {title}"

    try:
        log(
            f"YANDEX SEARCH: {query}"
        )

        result = client.search(
            query,
            type_="track",
            page=0
        )

        tracks = result.tracks

        if not tracks:
            log(
                f"YANDEX: не найдено — "
                f"{query}"
            )

            yandex_cache[cache_key] = None

            return None

        best = tracks.results[0]

        track_id = best.id

        album_id = None

        if best.albums:
            album_id = best.albums[0].id

        if not track_id or not album_id:
            log(
                f"YANDEX: найден трек, "
                f"но нет ID — {query}"
            )

            yandex_cache[cache_key] = None

            return None

        yandex_url = (
            "https://music.yandex.ru/album/"
            + str(album_id)
            + "/track/"
            + str(track_id)
        )

        yandex_cache[cache_key] = yandex_url

        log(
            f"YANDEX: {query} -> "
            f"{yandex_url}"
        )

        return yandex_url

    except Exception as error:
        log(
            f"Yandex search ERROR: "
            f"{type(error).__name__}: {error}"
        )

        yandex_cache[cache_key] = None

        return None


def fetch_lastfm_track():
    global cached_track
    global cached_status
    global last_fetch_time

    now = time.time()

    if now - last_fetch_time < CACHE_SECONDS:
        return cached_track, cached_status

    last_fetch_time = now

    if not LASTFM_API_KEY:
        log(
            "ERROR: LASTFM_API_KEY не задан"
        )

        cached_track = None
        cached_status = "error"

        return cached_track, cached_status

    if not LASTFM_USERNAME:
        log(
            "ERROR: LASTFM_USERNAME не задан"
        )

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

    url = (
        LASTFM_API_URL
        + "?"
        + urllib.parse.urlencode(params)
    )

    try:
        import urllib.request

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

            raw_data = response.read().decode(
                "utf-8"
            )

        data = json.loads(raw_data)

        if "error" in data:
            log(
                f"Last.fm ERROR "
                f"{data.get('error')}: "
                f"{data.get('message', 'Unknown error')}"
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
            log(
                "Last.fm: recent tracks пуст"
            )

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
            attributes.get("nowplaying")
            == "true"
        )

        artist_data = lastfm_track.get(
            "artist",
            {}
        )

        if isinstance(
            artist_data,
            dict
        ):
            artist = (
                artist_data.get(
                    "#text",
                    ""
                )
                or artist_data.get(
                    "name",
                    ""
                )
            )
        else:
            artist = str(
                artist_data
            )

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

        if isinstance(
            album_data,
            dict
        ):
            album = album_data.get(
                "#text",
                ""
            )
        else:
            album = str(
                album_data
            )

        album = album.strip()

        cover = ""

        images = lastfm_track.get(
            "image",
            []
        )

        if isinstance(
            images,
            list
        ):
            preferred_sizes = [
                "extralarge",
                "large",
                "medium",
                "small"
            ]

            for wanted_size in preferred_sizes:

                for image in images:

                    if not isinstance(
                        image,
                        dict
                    ):
                        continue

                    if image.get(
                        "size"
                    ) != wanted_size:
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

        # ==========================================
        # Yandex Music
        # ==========================================

        yandex_url = search_yandex_track(
            artist,
            title
        )

        # ==========================================
        # Текущий трек
        # ==========================================

        track = {
            "artist": artist,
            "title": title,
            "album": album,
            "album_id": "",
            "track_id": "",
            "cover": cover,
            "url": lastfm_track.get(
                "url",
                ""
            ),
            "yandex_url": yandex_url
        }

        cached_track = track

        cached_status = (
            "playing"
            if is_now_playing
            else "stopped"
        )

        log(
            f"LASTFM TRACK: "
            f"{artist} - {title} "
            f"| status: {cached_status} "
            f"| cover: "
            f"{'yes' if cover else 'no'}"
        )

        return (
            cached_track,
            cached_status
        )

    except Exception as error:

        log(
            f"Last.fm request ERROR: "
            f"{type(error).__name__}: {error}"
        )

        if cached_track is not None:
            return (
                cached_track,
                cached_status
            )

        cached_status = "error"

        return (
            None,
            cached_status
        )


class PulseSyncHandler(
    BaseHTTPRequestHandler
):

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

    def send_json(
        self,
        data,
        status=200
    ):

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

        if (
            self.path == "/"
            or self.path == "/track"
        ):

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8"
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

        path = urllib.parse.urlparse(
            self.path
        ).path

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

            track, status = (
                fetch_lastfm_track()
            )

            body = self.send_json({
                "track": track,
                "status": status
            })

            self.wfile.write(body)

            return

        body = json.dumps({
            "error": "Not found"
        }).encode("utf-8")

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

    def log_message(
        self,
        format,
        *args
    ):

        log(
            "%s - %s"
            % (
                self.address_string(),
                format % args
            )
        )


def main():

    log(
        "========================================"
    )

    log(
        "PulseSync Last.fm server starting..."
    )

    log(
        "========================================"
    )

    log(
        f"PORT: {PORT}"
    )

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

    log(
        "YANDEX_TOKEN: "
        + (
            "есть"
            if YANDEX_TOKEN
            else "НЕТ"
        )
    )

    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        PulseSyncHandler
    )

    log(
        f"PulseSync server started "
        f"on port {PORT}"
    )

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        log(
            "Server stopping..."
        )

    finally:

        server.server_close()


if __name__ == "__main__":
    main()
