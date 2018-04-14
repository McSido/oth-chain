""" Module containing utility functionality
"""

debug = False


def print_debug_info(msg):
    """ Print a debug message

    Only print if debug-mode is active

    Args:
        msg: Message that should be printed
    """
    if debug:
        print('### DEBUG ###', msg)


def set_debug():
    """ Active debug-mode
    """
    global debug
    debug = True
