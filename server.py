import time
import requests


PULSESYNC_URL = "http://127.0.0.1:2007/get_track"
RENDER_URL = "https://ympulsesync-server.onrender.com/update"


session = requests.Session()


def get_track():
    response = session.get(
        PULSESYNC_URL,
        timeout=3
    )

    response.raise_for_status()

    return response.json()


def send_to_render(data):
    response = session.post(
        RENDER_URL,
        json=data,
        timeout=10
    )

    response.raise_for_status()

    return response.text


while True:

    try:

        data = get_track()

        result = send_to_render(data)

        if data.get("track"):
            title = data["track"].get("title", "Без названия")

            artists = ", ".join(
                artist.get("name", "")
                for artist in data["track"].get("artists", [])
            )

            print(
                f"Отправлено: {artists} — {title}"
            )

        else:
            print("Отправлено: ничего не играет")

        print("Render:", result)

    except Exception as error:

        print("Ошибка:", error)

    time.sleep(2)
