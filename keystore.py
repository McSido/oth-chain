import pickle

from utils import print_debug_info


class Keystore:

    def __init__(self, filename):
        self.store = dict()
        self.filename = filename
        self.load()

    def load(self):
        try:
            with open(self.filename, 'rb') as file:
                self.store = pickle.load(file)
        except FileNotFoundError:
            print_debug_info(f'File not found: {self.filename}')
        except pickle.PickleError as e:
            print_debug_info(f'Error with pickle: {e}')
        except EOFError as e:
            print_debug_info(f'Error with file: {e}')

    def save(self):
        try:
            with open(self.filename, 'wb') as file:
                pickle.dump(self.store, file)
        except pickle.PickleError as e:
            print_debug_info(f'Error with pickle {e}')
        except OSError as e:
            print_debug_info(f'Error writing store to disk: {e}')

    def add_key(self, name, key):
        try:
            if self.store[name]:
                print_debug_info(
                    'Name already exists,' +
                    'use update if you want to change the respective key')
                return
        except KeyError:
            self.store[name] = key
        else:
            self.save()

    def update_key(self, name, key):
        try:
            if key == '':
                self.store.pop(name)
                return
            if self.store[name]:
                self.store[name] = key
        except KeyError:
            print_debug_info('Name not found, did you spell it right?')
        else:
            self.save()

    def resolve_name(self, name):
        try:
            return self.store[name]
        except KeyError:
            print(f'Key for name {name} not found')
            return 'Error'
