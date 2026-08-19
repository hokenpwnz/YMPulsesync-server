from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json
import os
import threading
import time

from yandex_music.ynison import simple


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))

YANDEX_TOKEN = os.environ.get("YANDEX_TOKEN")

current_data = {
    "track": None,
    "status": "stopped"
}

data_lock = threading.Lock()


# ==========================================================
# Получение текущего трека через Ynison
# ==========================================================

def get_ynison_state():

    if not YANDEX_TOKEN:
        print("YANDEX_TOKEN не задан")
        return

    try:

        state = simple.get_state(
            YANDEX_TOKEN,
            device_id="pulsesync-render"
        )

        player_state = state.player_state
        queue = player_state.player_queue
        status = player_state.status

        index = queue.current_playable_index
        playable_list = queue.playable_list

        if (
            index < 0
            or index >= len(playable_list)
        ):
            print("Ynison: сейчас нет трека")

            with data_lock:
                current_data = {
                    "track": None,
                    "status": "stopped"
                }

            return

        playable = playable_list[index]

        title = getattr(
            playable,
            "title",
            ""
        )

        track_id = getattr(
            playable,
            "track_id",
            None
        )

        if not track_id:

            track_id = getattr(
                playable,
                "id",
                None
            )

        artists = getattr(
            playable,
            "artists",
            []
        )

        artist_names = []

        for artist in artists:

            name = getattr(
                artist,
                "name",
                None
            )

            if name:
                artist_names.append(name)

        artist = ", ".join(
            artist_names
        )

        album_id = ""

        albums = getattr(
            playable,
            "albums",
            []
        )

        if albums:

            album_id = getattr(
                albums[0],
                "id",
                ""
            )

        cover = getattr(
            playable,
            "cover_uri",
            ""
        )

        if not cover:

            cover = getattr(
                playable,
                "coverUri",
                ""
            )

        if cover:

            cover = cover.replace(
                "%%",
                "200x200"
            )

            if not cover.startswith(
                "http"
            ):

                cover = (
                    "https://"
                    + cover
                )

        paused = getattr(
            status,
            "paused",
            False
        )

        playback_status = (
            "paused"
            if paused
            else "playing"
        )

        new_data = {
            "track": {
                "artist": artist,
                "title": title,
                "album_id": str(album_id),
                "track_id": str(track_id),
                "cover": cover
            },
            "status": playback_status
        }

        with data_lock:
            globals()["current_data"] = new_data

        print(
            "Ynison:",
            artist,
            "-",
            title,
            "|",
            playback_status
        )

    except Exception as error:

        print(
            "Ynison ERROR:",
            repr(error)
        )


# ==========================================================
# Фоновый цикл Ynison
# ==========================================================

def ynison_loop():

    print("Ynison поток запущен")

    while True:

        get_ynison_state()

        time.sleep(2)


# ==========================================================
# HTTP
# ==========================================================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        global current_data

        parsed = urlparse(
            self.path
        )

        # --------------------------------------------------
        # Получить текущий трек
        # --------------------------------------------------

        if parsed.path == "/track":

            with data_lock:

                response_data = current_data.copy()

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8"
            )

            self.send_header(
                "Cache-Control",
                "no-store"
            )

            self.send_header(
                "Access-Control-Allow-Origin",
                "*"
            )

            self.end_headers()

            self.wfile.write(
                json.dumps(
                    response_data,
                    ensure_ascii=False
                ).encode("utf-8")
            )

            return

        # --------------------------------------------------
        # Старый agent.py
        #
        # Оставляем специально для совместимости.
        # --------------------------------------------------

        if parsed.path == "/update":

            params = parse_qs(
                parsed.query
            )

            try:

                artist = params.get(
                    "artist",
                    [""]
                )[0]

                title = params.get(
                    "title",
                    [""]
                )[0]

                album_id = params.get(
                    "album_id",
                    [""]
                )[0]

                track_id = params.get(
                    "track_id",
                    [""]
                )[0]

                cover = params.get(
                    "cover",
                    [""]
                )[0]

                status = params.get(
                    "status",
                    ["stopped"]
                )[0]

                # Пока агент работает, он имеет приоритет.
                # Поэтому Ynison не будет ломать текущую систему.

                if title:

                    with data_lock:

                        current_data = {
                            "track": {
                                "artist": artist,
                                "title": title,
                                "album_id": album_id,
                                "track_id": track_id,
                                "cover": cover
                            },
                            "status": status
                        }

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )

                self.send_header(
                    "Access-Control-Allow-Origin",
                    "*"
                )

                self.end_headers()

                self.wfile.write(
                    b'{"ok":true}'
                )

            except Exception as error:

                self.send_response(500)

                self.end_headers()

                self.wfile.write(
                    str(error).encode(
                        "utf-8"
                    )
                )

            return

        self.send_response(404)
        self.end_headers()


# ==========================================================
# Запуск
# ==========================================================

if YANDEX_TOKEN:

    threading.Thread(
        target=ynison_loop,
        daemon=True
    ).start()

else:

    print(
        "YANDEX_TOKEN отсутствует — "
        "Ynison отключён"
    )


server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"PulseSync server started on port {PORT}"
)

server.serve_forever()
