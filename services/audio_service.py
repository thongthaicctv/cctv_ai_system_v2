import os
import threading
import winsound

from core.resource_paths import resource_path

SOUND_DIR = resource_path("assets", "sounds")


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


def record_error():
    play_sound("eror.wav")
