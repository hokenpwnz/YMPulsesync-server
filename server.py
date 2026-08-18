from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

HOST = "0.0.0.0"
PORT = 10000

current_track = {
    "track": None,
    "status": "stopped"
}


class Handler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):

        body = json.dumps(data).encode("utf-8")

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
            "Access-Control-Allow-Origin",
            "*"
        )
        self.send_header(
            "Cache-Control",
            "no-store"
        )
        self.end_headers()

        self.wfile.write(body)


    def do_GET(self):

        if self.path == "/track":

            self.send_json(current_track)
            return


        self.send_json(
            {
                "error": "Not found"
            },
            404
        )


    def do_POST(self):

        if self.path != "/update":
            self.send_json(
                {
                    "error": "Not found"
                },
                404
            )
            return


        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            body = self.rfile.read(length)

            data = json.loads(
                body.decode("utf-8")
            )

            current_track["track"] = data.get("track")
            current_track["status"] = data.get(
                "status",
                "stopped"
            )

            self.send_json(
                {
                    "ok": True
                }
            )

        except Exception as error:

            self.send_json(
                {
                    "error": str(error)
                },
                400
            )


server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"PulseSync server listening on port {PORT}"
)

server.serve_forever()
