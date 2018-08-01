import re


class CLI:
    @staticmethod
    def _get_command():
        try:
            command = input()
            command = re.sub(r'\s\s*', ' ', command.lower().strip())
            return command
        except KeyboardInterrupt:
            print('Detected Keyboard interrupt, exiting program')

    @staticmethod
    def process_command():

        def help(*kwargs):
            pass

        def exit(*kwargs):
            pass

        def mine(*kwargs):
            pass

        def transaction(*kwargs):
            pass

        def dump(*kwargs):
            pass

        def peers(*kwargs):
            pass

        def save_key(*kwargs):
            pass

        def import_key(*kwargs):
            pass

        def delete_key(*kwargs):
            pass

        def export_key(*kwargs):
            pass

        def balance(*kwargs):
            pass

        def save_chain(*kwargs):
            pass

        def open_gui(*kwargs):
            pass

        commands = {
            'help': help,
            'exit': exit,
            'mine': mine,
            'transaction': transaction,
            'dump': dump,
            'peers': peers,
            'key': save_key,
            'import': import_key,
            'delete': delete_key,
            'export': export_key,
            'balance': balance,
            'save': save_chain,
            'gui': open_gui
        }

        def processor(command, *kwargs):
            return commands[command](kwargs)
