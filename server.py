from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
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

        # Получить текущий трек
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

        # Получить данные от agent.py
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

        self.send_response(404)
        self.end_headers()


server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"PulseSync server started on port {PORT}"
)

server.serve_forever()
