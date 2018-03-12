debug = False


def print_debug_info(msg):
    if debug:
        print(msg)


def set_debug():
    global debug
    debug = True
