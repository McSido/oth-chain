""" Stresstest module for the blockchain client,
    contains some tests to see how well the
    blockchain works under normal usage

    Not very extensive, should be redone to work
    with py.test
"""
import asyncio
import io
import random
import sys
import time
import getopt
from asyncio.subprocess import PIPE, STDOUT


class TestCase(object):
    """ Class to be used in the tests
    Change planned_commands, expectation_test,
    expected_output, expectation_true, expectation_false
    depening on current test
    """

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
        """ Returns one of the planned commands in order
        """
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
        """ Test the input against the expectation
            Arguments:
                result -> Result to be compared against expectations
            Returns:
                string containing expectation result
        """
        if not result.startswith(self.expectation_test):
            return ''

        assert result.strip() == self.expected_output

        if result.strip() == self.expected_output:
            return self.expectation_true
        else:
            return self.expectation_false


current_test = TestCase()  # testcase used in planned_test


def current_time():
    """Returns current time
    """
    t = time.localtime()[3:6]
    return f'({t[0]}:{t[1]}:{t[2]})'


def create_random_transaction():
    """ Returns a random transaction
    accounts = [a,b,c]
    amount = [1-100]
    """
    accounts = [
        'a',
        'b',
        'c'
    ]
    return 'transaction ' + \
        accounts[random.randint(0, len(accounts))-1] + ' ' + \
        str(random.randint(1, 100))


def get_random_command():
    """Returns a random command
    Possible commands:
    - mine
    - transaction (random)
    - exit
    """
    command = random.randint(1, 50)
    if command < 15:
        return 'mine'
    elif command < 48:
        return create_random_transaction()
    else:
        return 'exit'


async def run_planned_command(*args):
    """Async function to run the planned stresstest,
    using the global current_test
    """
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
    """Async function to run the random stresstest
    """
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
    """ Run a planned test on the blockchain using the current_test object
    """

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
    """ Run a stress test that uses get_random_command()
    to execute random commands on the blockchain
    """
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
    """ Setup the test environment for py.test
        Currently unimplemented
    """
    pass


def main(argv=sys.argv):
    """ Main function of the stresstest
    """
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
