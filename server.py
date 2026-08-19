from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
import json
import os

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))

current_data = {
    "track": None,
    "status": "stopped"
}


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        global current_data

        parsed = urlparse(self.path)

        # ==================================================
        # Получить текущий трек
        # ==================================================

        if parsed.path == "/track":

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
                    current_data,
                    ensure_ascii=False
                ).encode("utf-8")
            )

            return


        # ==================================================
        # Получить текущую обложку
        # ==================================================

        if parsed.path == "/cover":

            try:

                track = current_data.get("track")

                if not track:
                    self.send_response(404)
                    self.end_headers()
                    return


                cover_url = track.get("cover")

                if not cover_url:
                    self.send_response(404)
                    self.end_headers()
                    return


                # Если PulseSync передал URL без протокола
                if not cover_url.startswith("http://") and not cover_url.startswith("https://"):
                    cover_url = "https://" + cover_url


                request = Request(
                    cover_url,
                    headers={
                        "User-Agent": "Mozilla/5.0"
                    }
                )


                with urlopen(
                    request,
                    timeout=10
                ) as response:

                    image = response.read()

                    content_type = response.headers.get(
                        "Content-Type",
                        "image/jpeg"
                    )


                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    content_type
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

                self.wfile.write(image)

            except Exception as error:

                print(
                    "Cover error:",
                    error
                )

                self.send_response(500)
                self.end_headers()

            return


        # ==================================================
        # Получить данные от agent.py
        # ==================================================

        if parsed.path == "/update":

            params = parse_qs(parsed.query)

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


                if not title:

                    current_data = {
                        "track": None,
                        "status": "stopped"
                    }

                else:

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
                    str(error).encode("utf-8")
                )

            return


        # ==================================================
        # Неизвестный адрес
        # ==================================================

        self.send_response(404)
        self.end_headers()


# ==================================================
# Запуск сервера
# ==================================================

server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"PulseSync server started on port {PORT}"
)

server.serve_forever()
