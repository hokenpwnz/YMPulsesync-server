```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import json
import os
import threading
import time

from yandex_music import Client
from yandex_music.ynison import simple


# ==========================================================
# Настройки
# ==========================================================

HOST = "0.0.0.0"

PORT = int(
    os.environ.get(
        "PORT",
        10000
    )
)

YANDEX_TOKEN = os.environ.get(
    "YANDEX_TOKEN"
)


# ==========================================================
# Текущее состояние
# ==========================================================

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

        client = Client(
            YANDEX_TOKEN
        ).init()

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

else:

    print(
        "YANDEX_TOKEN отсутствует",
        flush=True
    )


# ==========================================================
# Получение метаданных трека
# ==========================================================

def get_track_metadata(track_id):

    if not client:
        return None

    if not track_id:
        return None

    try:

        tracks = client.tracks(
            [
                str(track_id)
            ]
        )

        if not tracks:
            return None

        track = tracks[0]


        # --------------------------------------------------
        # Исполнитель
        # --------------------------------------------------

        artist_names = []

        for artist in (
            track.artists or []
        ):

            name = getattr(
                artist,
                "name",
                None
            )

            if name:
                artist_names.append(
                    name
                )


        artist = ", ".join(
            artist_names
        )


        # --------------------------------------------------
        # Альбом
        # --------------------------------------------------

        album_id = ""

        if track.albums:

            album_id = getattr(
                track.albums[0],
                "id",
                ""
            )


        # --------------------------------------------------
        # Результат
        # --------------------------------------------------

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


        # --------------------------------------------------
        # Состояние плеера
        # --------------------------------------------------

        player_state = (
            state.player_state
        )

        queue = (
            player_state.player_queue
        )

        status = (
            player_state.status
        )


        index = (
            queue.current_playable_index
        )

        playable_list = (
            queue.playable_list
        )


        # --------------------------------------------------
        # Проверяем очередь
        # --------------------------------------------------

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


        playable = (
            playable_list[index]
        )


        # --------------------------------------------------
        # Данные Ynison
        # --------------------------------------------------

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


        # --------------------------------------------------
        # Обложка
        # --------------------------------------------------

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


        # --------------------------------------------------
        # Метаданные через API
        # --------------------------------------------------

        metadata = get_track_metadata(
            track_id
        )


        artist = ""


        if metadata:

            artist = metadata.get(
                "artist",
                ""
            )


            if metadata.get(
                "title"
            ):

                title = metadata[
                    "title"
                ]


            if metadata.get(
                "album_id"
            ):

                album_id = metadata[
                    "album_id"
                ]


        # --------------------------------------------------
        # Статус
        # --------------------------------------------------

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


        # --------------------------------------------------
        # URL Яндекс Музыки
        # --------------------------------------------------

        track_url = ""


        if album_id and track_id:

            track_url = (
                "https://music.yandex.ru/album/"
                + str(album_id)
                + "/track/"
                + str(track_id)
            )


        # --------------------------------------------------
        # Формируем состояние
        # --------------------------------------------------

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

                "url": track_url
            },

            "status": playback_status
        }


        # --------------------------------------------------
        # Сохраняем
        # --------------------------------------------------

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

        try:

            get_ynison_state()

        except Exception as error:

            print(
                "Ynison LOOP ERROR:",
                repr(error),
                flush=True
            )


        time.sleep(
            2
        )


# ==========================================================
# HTTP Handler
# ==========================================================

class Handler(
    BaseHTTPRequestHandler
):


    # ------------------------------------------------------
    # Логи
    # ------------------------------------------------------

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
    # HEAD
    # ------------------------------------------------------

    def do_HEAD(self):

        self.send_response(
            200
        )

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


            self.send_response(
                200
            )

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
                ).encode(
                    "utf-8"
                )
            )

            return


        # ==================================================
        # /cover
        #
        # Twitch обращается сюда.
        #
        # Render сам скачивает картинку
        # с avatars.yandex.net и отдаёт её Twitch.
        # ==================================================

        if parsed.path == "/cover":

            with data_lock:

                track = (
                    current_data.get(
                        "track"
                    )
                )


            if not track:

                self.send_response(
                    404
                )

                self.end_headers()

                return


            cover_url = (
                track.get(
                    "cover",
                    ""
                )
            )


            if not cover_url:

                self.send_response(
                    404
                )

                self.end_headers()

                return


            try:

                print(
                    "Cover proxy:",
                    cover_url,
                    flush=True
                )


                request = Request(

                    cover_url,

                    headers={
                        "User-Agent":
                            "Mozilla/5.0 "
                            "(Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 "
                            "Chrome/151.0 Safari/537.36"
                    }
                )


                with urlopen(
                    request,
                    timeout=10
                ) as response:

                    image_data = (
                        response.read()
                    )

                    content_type = (
                        response.headers.get(
                            "Content-Type",
                            "image/jpeg"
                        )
                    )


                self.send_response(
                    200
                )

                self.send_header(
                    "Content-Type",
                    content_type
                )

                self.send_header(
                    "Content-Length",
                    str(
                        len(image_data)
                    )
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
                    image_data
                )


                print(
                    "Cover proxy: OK",
                    len(image_data),
                    "bytes",
                    flush=True
                )


            except Exception as error:

                print(
                    "Cover proxy ERROR:",
                    repr(error),
                    flush=True
                )


                self.send_response(
                    502
                )

                self.send_header(
                    "Content-Type",
                    "text/plain; charset=utf-8"
                )

                self.end_headers()


                self.wfile.write(
                    b"Cover proxy error"
                )


            return


        # ==================================================
        # /health
        # ==================================================

        if parsed.path == "/health":

            self.send_response(
                200
            )

            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )

            self.end_headers()


            self.wfile.write(
                b"OK"
            )

            return


        # ==================================================
        # 404
        # ==================================================

        self.send_response(
            404
        )

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


# ==========================================================
# Запускаем Ynison
# ==========================================================

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


# ==========================================================
# HTTP сервер
# ==========================================================

server = ThreadingHTTPServer(
    (
        HOST,
        PORT
    ),
    Handler
)


print(
    "PulseSync server started on port",
    PORT,
    flush=True
)


server.serve_forever()
```
