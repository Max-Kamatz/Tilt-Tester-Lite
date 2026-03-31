# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
