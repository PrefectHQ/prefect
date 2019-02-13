import curses
import os
import time


def load_images():
    images = []
    cur_path = os.path.dirname(__file__)
    img_path = os.path.join(cur_path, "_sig29/{}.txt")
    for i in range(1, 7):
        images.append(open(img_path.format(i), "r").read())
    return images


def sig_handler(*args, **kwargs):
    images = load_images()
    num_iters = 5
    try:
        screen = curses.initscr()
        width = screen.getmaxyx()[1]
        height = screen.getmaxyx()[0]
        size = width * height
        start_pos = (width - 60) // 2

        if width < 60 or height < 35:
            curses.endwin()
            num_iters = 0

        curses.curs_set(0)
        screen.clear()

        for _ in range(num_iters):
            for img in images:
                for line_no, line in enumerate(img.split("\n")):
                    for char_no, char in enumerate(line):
                        screen.addstr(line_no, char_no + start_pos, char)

                time.sleep(0.1)
                screen.refresh()
                screen.timeout(30)
            if screen.getch() != -1:
                break
    except:
        pass
    finally:
        curses.endwin()
