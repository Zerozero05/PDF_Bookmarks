"""Launch the GUI; files dropped onto the EXE icon arrive as arguments."""

import sys

from bookmarks_gui import launch


if __name__ == "__main__":
    launch(sys.argv[1:])
