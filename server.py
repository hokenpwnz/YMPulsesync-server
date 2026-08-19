from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
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

debug_data = {
    "playable": "",
    "playable_dict": "",
    "playable_type": "",
    "error": None
}

data_lock = threading.Lock()


# ==========================================================
# Получение состояния через Ynison
# ==========================================================

def get_ynison_state():

    if not YANDEX_TOKEN:
        print(
            "ERROR: YANDEX_TOKEN не задан",
            flush=True
        )
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
                current_data.clear()
                current_data.update({
                    "track": None,
                    "status": "stopped"
                })

            print(
                "Ynison: сейчас ничего не играет",
                flush=True
            )

            return

        playable = playable_list[index]


        # ==================================================
        # Сохраняем диагностическую информацию
        # ==================================================

        playable_dict = getattr(
            playable,
            "__dict__",
            {}
        )

        with data_lock:

            debug_data["playable"] = str(
                playable
            )

            debug_data["playable_dict"] = str(
                playable_dict
            )

            debug_data["playable_type"] = str(
                type(playable)
            )

            debug_data["error"] = None


        print(
            "YNISON PLAYABLE:",
            str(playable),
            flush=True
        )

        print(
            "YNISON PLAYABLE DICT:",
            str(playable_dict),
            flush=True
        )


        # ==================================================
        # Название
        # ==================================================

        title = getattr(
            playable,
            "title",
            ""
        )


        # ==================================================
        # Исполнитель
        # ==================================================

        artist = ""

        artists = getattr(
            playable,
            "artists",
            None
        )

        if artists:

            names = []

            for item in artists:

                name = getattr(
                    item,
                    "name",
                    None
                )

                if name:
                    names.append(
                        name
                    )

            artist = ", ".join(names)


        # ==================================================
        # ID трека
        # ==================================================

        track_id = getattr(
            playable,
            "track_id",
            None
        )

        if track_id is None:

            track_id = getattr(
                playable,
                "id",
                None
            )


        # ==================================================
        # ID альбома
        # ==================================================

        album_id = ""

        albums = getattr(
            playable,
            "albums",
            None
        )

        if albums:

            first_album = albums[0]

            album_id = getattr(
                first_album,
                "id",
                ""
            )


        # ==================================================
        # Обложка
        # ==================================================

        cover = getattr(
            playable,
            "cover_uri",
            None
        )

        if not cover:

            cover = getattr(
                playable,
                "coverUri",
                None
            )

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
        # Сохраняем результат
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

                "cover": cover or ""
            },

            "status": playback_status
        }


        with data_lock:

            current_data.clear()

            current_data.update(
                new_data
            )


        print(
            "Ynison:",
            artist or "[без исполнителя]",
            "-",
            title,
            "|",
            "album:",
            album_id,
            "|",
            "track:",
            track_id,
            flush=True
        )


    except Exception as error:

        with data_lock:

            debug_data["error"] = repr(
                error
            )


        print(
            "Ynison ERROR:",
            repr(error),
            flush=True
        )


# ==========================================================
# Фоновый поток
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

class Handler(BaseHTTPRequestHandler):

    def log_message(
        self,
        format,
        *args
    ):

        print(
            format % args,
            flush=True
        )


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
        # /debug
        # ==================================================

        if parsed.path == "/debug":

            with data_lock:

                response = json.loads(
                    json.dumps(
                        debug_data,
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
        # Всё остальное
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
    "есть" if YANDEX_TOKEN else "НЕТ",
    flush=True
)


if YANDEX_TOKEN:

    threading.Thread(
        target=ynison_loop,
        daemon=True
    ).start()

else:

    print(
        "Ynison не запущен: отсутствует YANDEX_TOKEN",
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
