import asyncio
import io
import random
import sys
import time
import getopt
from asyncio.subprocess import PIPE, STDOUT


class TestCase(object):

    command_counter = -1

    planned_commands = [
        'mine',
        'mine',
        'transaction a 10',
        'transaction b 20',
        'mine',
        'balance',  # should be 50+50-(10+1)-(20+1)+(50+1+1)
        'exit'
    ]

    def get_command(self):
        self.command_counter += 1
        return self.planned_commands[self.command_counter]

    expectation_test = 'Current Balance:'
    expected_output = f'Current Balance: {50+50-(10+1)-(20+1)+(50+1+1)}'
    expectation_true = '''    =============================
    =========Test passed=========
    √√√√ Balance as expected √√√√
    =============================
    =============================
    '''
    expectation_false = '''    =============================
    =========Test failed=========
    XXXX WRONG Balance XXXX!
    =============================
    =============================
    '''

    def test_expectation(self, result):
        if not result.startswith(self.expectation_test):
            return ''
        elif result.strip() == self.expected_output:
            return self.expectation_true
        else:
            return self.expectation_false


current_test = TestCase()


def current_time():
    t = time.localtime()[3:6]
    return f'({t[0]}:{t[1]}:{t[2]})'


def create_random_transaction():
    accounts = [
        'a',
        'b',
        'c'
    ]
    return 'transaction ' + \
        accounts[random.randint(0, len(accounts))-1] + ' ' + \
        str(random.randint(1, 100))


def get_random_command():
    command = random.randint(1, 50)
    if command < 15:
        return 'mine'
    elif command < 48:
        return create_random_transaction()
    else:
        return 'exit'


async def run_planned_command(*args):
    proc = await asyncio.create_subprocess_exec(*args,
                                                stdin=PIPE,
                                                stdout=PIPE,
                                                )

    while True:

        if random.randint(1, 100) < 5:  # Add random element
            com = current_test.get_command()
            print(f'### {current_time()} Execute: {com}')
            proc.stdin.write(bytes(com.encode('utf-8')) + b'\n')

        try:
            line = await asyncio.wait_for(proc.stdout.readline(), 0.01)
        except asyncio.TimeoutError:
            pass
        else:
            if not line:
                break
            else:
                rec = line.decode('utf-8')
                print(rec)
                print(current_test.test_expectation(rec))
        time.sleep(0.01)
    return await proc.wait()


async def run_random_command(*args):
    proc = await asyncio.create_subprocess_exec(*args,
                                                stdin=PIPE,
                                                stdout=PIPE,
                                                )

    while True:

        if random.randint(1, 100) < 5:
            com = get_random_command()
            print(f'### {current_time()} Execute: {com}')
            proc.stdin.write(bytes(com.encode('utf-8')) + b'\n')

        try:
            line = await asyncio.wait_for(proc.stdout.readline(), 0.01)
        except asyncio.TimeoutError:
            pass
        else:
            if not line:
                break
            else:
                rec = line.decode('utf-8')
                print(rec)
        time.sleep(0.01)
    return await proc.wait()


def planned_test(port=7777, test_type='balance'):

    if test_type == 'balance':
        pass
    elif test_type == '':
        pass

    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()  # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    print(f'### {current_time()} Starting on port: {port}:')
    loop.run_until_complete(
        run_planned_command(
            'python',
            'core.py',
            f'--port={port}',
            '--store=keys_abc'
        ))


def random_stress_test(port=7777):
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()  # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    while True:
        print(f'### {current_time()} Starting on port: {port}:')
        loop.run_until_complete(
            run_random_command(
                'python',
                'core.py',
                f'--port={port}',
                '--store=keys_abc'
            ))
        time.sleep(random.randint(1, 5))


def setup_test_environment():
    pass


def main(argv=sys.argv):
    port = 7777
    try:
        opts, args = getopt.getopt(argv[1:], 'p=', ['port='])
        for o, a in opts:
            if o in ('-p', '--port'):
                try:
                    port = int(a)
                except:
                    print("Port was invalid (e.g. not an int)")
    except getopt.GetoptError as err:
        print(err)

    planned_test(port)


if __name__ == '__main__':
    main()
