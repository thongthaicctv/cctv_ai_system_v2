import os
import threading
import winsound


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SOUND_DIR = os.path.join(BASE_DIR, "assets", "sounds")


def _play(filename):
    path = os.path.join(SOUND_DIR, filename)

    if os.path.exists(path):
        winsound.PlaySound(
            path,
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    else:
        winsound.MessageBeep()


def play_sound(filename):
    threading.Thread(
        target=_play,
        args=(filename,),
        daemon=True
    ).start()


def employee_ok():
    play_sound("employee_ok.wav")


def order_ok():
    play_sound("order_ok.wav")


def stop_ok():
    play_sound("stop_ok.wav")