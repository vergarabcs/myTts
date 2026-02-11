import sys

from PySide6 import QtWidgets

from src.epub_reader import EpubReaderApp


def main():
    print("Starting EPUB reader...", file=sys.stderr, flush=True)
    qt_app = QtWidgets.QApplication(sys.argv)
    window = EpubReaderApp()
    window.resize(1000, 700)
    window.show()
    print("UI initialized, entering Qt event loop", file=sys.stderr, flush=True)
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
