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

debug_data = {
    "playable": None,
    "playable_dict": None,
    "playable_type": None,
    "error": None
}

data_lock = threading.Lock()


# ==========================================================
# Ynison
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

            print(
                "Ynison: сейчас нет трека",
                flush=True
            )

            with data_lock:

                globals()["current_data"] = {
                    "track": None,
                    "status": "stopped"
                }

            return


        playable = playable_list[index]


        # ==================================================
        # DEBUG
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
        # ID трека
        # ==================================================

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


        # ==================================================
        # Исполнитель
        # ==================================================

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

                artist_names.append(
                    name
                )


        artist = ", ".join(
            artist_names
        )


        # ==================================================
        # Альбом
        # ==================================================

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


        # ==================================================
        # Обложка
        # ==================================================

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
        # Данные для Twitch
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

                "cover": cover
            },

            "status": playback_status
        }


        with data_lock:

            globals()["current_data"] = (
                new_data
            )


        print(
            "Ynison:",
            artist,
            "-",
            title,
            "|",
            playback_status,
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
# Фоновый цикл Ynison
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
# HTTP SERVER
# ==========================================================

class Handler(
    BaseHTTPRequestHandler
):


    # ------------------------------------------------------
    # Отключаем лишний стандартный лог для каждого запроса
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


    def do_GET():

        pass
