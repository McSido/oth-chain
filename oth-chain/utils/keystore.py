import serializer

from .utils import print_debug_info


def load_key(filename):
    """ Attempts to load a key from the provided file.

    Args:
        filename: Specifies the key file.
    """
    with open(filename, 'r') as f:
        return serializer.deserialize(f.read())


def save_key(key, filename):
    """ Attempts to save the provided key to the provided file.

    Args:
        key: The key to be saved.
        filename: The filename of the saved key.
    """
    with open(filename, 'w') as f:
        f.write(serializer.serialize(key))


class Keystore:

    def __init__(self, filename):
        self.store = dict()
        self.filename = filename
        self.load()

    def load(self):
        try:
            with open(self.filename, 'r') as file:
                self.store = serializer.deserialize(file.read())
        except FileNotFoundError:
            print_debug_info(f'File not found: {self.filename}')
        except EOFError as e:
            print_debug_info(f'Error with file: {e}')

    def save(self):
        try:
            with open(self.filename, 'w') as file:
                file.write(serializer.serialize(self.store))
        except OSError as e:
            print_debug_info(f'Error writing store to disk: {e}')

    def add_key(self, name, key_name):
        key = load_key(key_name)
        try:
            if self.store[name]:
                print_debug_info(
                    'Name already exists,' +
                    'use update if you want to change the respective key')
                return key, False
        except KeyError:
            self.store[name] = key
        else:
            self.save()
        return key, True

    def update_key(self, name, key_name):
        old_key = None
        try:
            if key_name == '':
                self.store.pop(name)
                return
            if self.store[name]:
                key = load_key(key_name)
                old_key = self.store[name]
                self.store[name] = key
        except KeyError:
            print_debug_info('Name not found, did you spell it right?')
        else:
            self.save()
        return old_key

    def resolve_name(self, name):
        try:
            return self.store[name]
        except KeyError:
            print(f'Key for name {name} not found')
            return 'Error'
