"""Arduino App Lab Python entry point."""

from app_core import main


try:
    from arduino.app_utils import App
except Exception:
    App = None


if App is None:
    def run() -> None:
        main()
else:
    def run() -> None:
        App.run(user_loop=main)


if __name__ == "__main__":
    run()
