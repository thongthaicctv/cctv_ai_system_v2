import os
import sys


def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))


def bundle_base_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return app_base_dir()


def app_path(*parts):
    return os.path.join(app_base_dir(), *parts)


def resource_path(*parts):
    return os.path.join(bundle_base_dir(), *parts)
