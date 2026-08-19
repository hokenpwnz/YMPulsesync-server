from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json
import os
import threading
import time

from yandex_music import Client
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
# Yandex Music API
# ==========================================================

client = None

if YANDEX_TOKEN:
    try:
        client = Client(YANDEX_TOKEN).init()

        print(
            "Yandex Music API: OK",
            flush=True
        )

    except Exception as error:

        print(
            "Yandex Music API ERROR:",
            repr(error),
            flush=True
        )


# ==========================================================
# Получение метаданных трека
# ==========================================================

def get_track_metadata(track_id):

    if not client:
        return None

    try:

        tracks = client.tracks(
            [str(track_id)]
        )

        if not tracks:
            return None

        track = tracks[0]

        artist_names = []

        for artist in track.artists or []:

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

        if track.albums:

            album_id = getattr(
                track.albums[0],
                "id",
                ""
            )

        return {
            "artist": artist,
            "title": getattr(
                track,
                "title",
                ""
            ),
            "album_id": str(
                album_id
            ),
            "track_id": str(
                track_id
            )
        }

    except Exception as error:

        print(
            "Metadata ERROR:",
            repr(error),
            flush=True
        )

        return None


# ==========================================================
# Получение состояния Ynison
# ==========================================================

def get_ynison_state():

    global current_data

    if not YANDEX_TOKEN:
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

            with data_lock:

                current_data = {
                    "track": None,
                    "status": "stopped"
                }

            return


        playable = playable_list[index]


        # ==================================================
        # Данные непосредственно из Ynison
        # ==================================================

        track_id = getattr(
            playable,
            "playable_id",
            ""
        )

        album_id = getattr(
            playable,
            "album_id_optional",
            ""
        )

        title = getattr(
            playable,
            "title",
            ""
        )

        cover = getattr(
            playable,
            "cover_url_optional",
            ""
        )


        # ==================================================
        # Обложка
        # ==================================================

        if cover:

            cover = cover.replace(
                "%%",
                "200x200"
            )

            if not cover.startswith(
                "http://"
            ) and not cover.startswith(
                "https://"
            ):

                cover = (
                    "https://"
                    + cover
                )


        # ==================================================
        # Получаем исполнителя через API
        # ==================================================

        metadata = get_track_metadata(
            track_id
        )


        artist = ""

        if metadata:

            artist = metadata.get(
                "artist",
                ""
            )

            # API является источником
            # истины для album_id/title

            if metadata.get(
                "album_id"
            ):

                album_id = metadata[
                    "album_id"
                ]

            if metadata.get(
                "title"
            ):

                title = metadata[
                    "title"
                ]


        # ==================================================
        # Статус
        # ==================================================

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


        # ==================================================
        # Формируем данные
        # ==================================================

        new_data = {

            "track": {

                "artist": artist,

                "title": title,

                "album_id": str(
                    album_id
                ),

                "track_id": str(
                    track_id
                ),

                "cover": cover,

                "url": (
                    "https://music.yandex.ru/album/"
                    + str(album_id)
                    + "/track/"
                    + str(track_id)
                )
            },

            "status": playback_status
        }


        with data_lock:

            current_data = new_data


        print(
            "TRACK:",
            artist or "[без исполнителя]",
            "-",
            title,
            "| album:",
            album_id,
            "| track:",
            track_id,
            flush=True
        )


    except Exception as error:

        print(
            "Ynison ERROR:",
            repr(error),
            flush=True
        )


# ==========================================================
# Фоновый Ynison
# ==========================================================

def ynison_loop():

    print(
        "Ynison поток запущен",
        flush=True
    )

    while True:

        get_ynison_state()

        time.sleep(2)


# ==========================================================
# HTTP
# ==========================================================

class Handler(
    BaseHTTPRequestHandler
):

    def log_message(
        self,
        format,
        *args
    ):

        print(
            format % args,
            flush=True
        )


    # ------------------------------------------------------
    # Render health check
    # ------------------------------------------------------

    def do_HEAD(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()


    # ------------------------------------------------------
    # GET
    # ------------------------------------------------------

    def do_GET(self):

        parsed = urlparse(
            self.path
        )


        # ==================================================
        # /track
        # ==================================================

        if parsed.path == "/track":

            with data_lock:

                response = json.loads(
                    json.dumps(
                        current_data,
                        ensure_ascii=False
                    )
                )


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
                    response,
                    ensure_ascii=False
                ).encode("utf-8")
            )

            return


        # ==================================================
        # /cover
        # ==================================================

        if parsed.path == "/cover":

            with data_lock:

                track = current_data.get(
                    "track"
                )

                cover = (
                    track.get("cover", "")
                    if track
                    else ""
                )


            response = {
                "cover": cover
            }


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
                    response,
                    ensure_ascii=False
                ).encode("utf-8")
            )

            return


        # ==================================================
        # 404
        # ==================================================

        self.send_response(404)

        self.end_headers()


# ==========================================================
# Запуск
# ==========================================================

print(
    "PulseSync server starting...",
    flush=True
)

print(
    "PORT:",
    PORT,
    flush=True
)

print(
    "YANDEX_TOKEN:",
    "есть"
    if YANDEX_TOKEN
    else "НЕТ",
    flush=True
)


if YANDEX_TOKEN:

    threading.Thread(
        target=ynison_loop,
        daemon=True
    ).start()

else:

    print(
        "ERROR: YANDEX_TOKEN отсутствует",
        flush=True
    )


server = ThreadingHTTPServer(
    (
        HOST,
        PORT
    ),
    Handler
)


print(
    f"PulseSync server started on port {PORT}",
    flush=True
)

server.serve_forever()
