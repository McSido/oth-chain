import asyncio
import io
import random
import sys
import time
from asyncio.subprocess import PIPE, STDOUT


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


def get_command():
    yield 'mine'
    yield 'mine'
    yield 'transaction a 10'
    yield 'transaction b 20'
    yield 'mine'
    yield 'balance'  # should be 50+50-(10+1)-(20+1)+(50+1+1)


def get_expected():
    yield 50+50-(10+1)-(20+1)+(50+1+1)


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

    commands = [
        'mine',
        'mine',
        'transaction a 10',
        'transaction b 20',
        'mine',
        'balance',  # should be 50+50-(10+1)-(20+1)+(50+1+1)
        'exit'
    ]
    counter = 0

    while True:

        if random.randint(1, 100) < 5:
            com = commands[counter]
            counter += 1
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
                if rec.startswith('Current Balance: '):
                    if int(rec.split(':')[1]) == 50+50-(10+1)-(20+1)+(50+1+1):
                        print('----------- Balance as expected !')
                        return
                    else:
                        print('----------- WRONG Balance !!!')
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


def planned_test(port=7777):
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


def main():
    try:
        planned_test(sys.argv[1])
    except:
        planned_test()


if __name__ == '__main__':
    main()
