import sys
import tkinter as tk

from src.epub_reader import EpubReaderApp


def main():
    print("Starting EPUB reader...", file=sys.stderr, flush=True)
    root = tk.Tk()
    print("Tk root created", file=sys.stderr, flush=True)
    root.geometry("900x600")
    app = EpubReaderApp(root)
    print("UI initialized, entering mainloop", file=sys.stderr, flush=True)
    root.mainloop()


if __name__ == "__main__":
    main()
