import utils


def test_debug_info(capsys):
    utils.set_debug()
    utils.print_debug_info('TEST')

    captured = capsys.readouterr()
    assert captured.out == '### DEBUG ### TEST\n'


def test_key(tmpdir):
    key = 'ABC'

    path = tmpdir.mkdir('key').join('key1')

    utils.save_key(key, path)

    assert utils.load_key(path) == key


def test_keystore(tmpdir):

    key = 'ABC'

    store_path = tmpdir.mkdir('key').join('store')
    key_path = tmpdir.join('key').join('key1')
    utils.save_key(key, key_path)

    store = utils.Keystore(store_path)

    assert store.add_key('TEST', key_path)[1]
    store.update_key('TEST', key_path)

    assert store.resolve_name('TEST') == key

    assert not store.add_key('TEST', key_path)[1]

    assert store.resolve_name('1234') == 'Error'

    # Test saving

    store = utils.Keystore(store_path)
    assert store.resolve_name('TEST') == key
