'''
Common utilities used accross modules
'''

# Python imports
import os
import sys

from clara.model import EOF


class UnknownLanguage(Exception):
    '''
    Signals use of unknown language either in parser or interpreter.
    '''


DEBUG_DEST = sys.stderr
ERROR_DEST = sys.stderr

DEBUG = False


def debug(msg, *args):
    if not DEBUG:
        return
    if args:
        msg %= tuple(args)
    print('[debug] %s' % (msg,), file=DEBUG_DEST)


def error(msg, *args):
    if args:
        msg %= tuple(args)
    print('[error] %s' % (msg,), file=ERROR_DEST)


def get_option(cf, section, option, default=None):
    '''
    Safe option getter with default value
    '''

    if cf.has_option(section, option):
        return cf.get(section, option)
    else:
        return default


def get_int_option(cf, section, option, default=None):
    '''
    Safe (int) option getter with default value
    '''

    if cf.has_option(section, option):
        return cf.getint(section, option)
    else:
        return default


def get_bool_option(cf, section, option, default=None):
    '''
    Safe (bool) option getter with default value
    '''

    if cf.has_option(section, option):
        return cf.getboolean(section, option)
    else:
        return default


def parseargs(argvs):
    '''
    Simple argument parser
    '''

    args = []
    kwargs = {}

    nextopt = None

    for arg in argvs:
        if nextopt:
            kwargs[nextopt] = arg
            nextopt = None

        elif arg.startswith('--'):
            nextopt = arg[2:]

        elif arg.startswith('-'):
            kwargs[arg[1:]] = True

        else:
            args.append(arg)

    return args, kwargs


def cleanstr(s):
    '''
    Strips \n\r\t from a string
    Changes \n\r\t to literals
    '''

    s = s.strip(' \t\r\n\\t\\r\\n')
    s = s.replace('\r\n', '\\n')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')

    return s


def equals(v1, v2):
    '''
    Different equality

    (mainly because different representations of two "same" floats)
    '''

    # List and tuples
    if ((isinstance(v1, list) and isinstance(v2, list))
            or (isinstance(v1, tuple) and isinstance(v2, tuple))):

        if len(v1) != len(v2):
            return False

        for e1, e2 in zip(v1, v2):
            if not equals(e1, e2):
                return False

        return True

    # Do we need this for any other structures (e.g., dict)?

    # Floats
    if isinstance(v1, float) and isinstance(v2, float):
        # Two floats with the same string representation can be differently
        # represented in memory, so their equality test with == fails.
        # However, when converted to strings first, they have the same
        # representation also in memory
        return float(str(v1)) == float(str(v2))

    # Other values
    return v1 == v2


def get_mem_filter(variable_name):
    def do_filter(mem):
        return mem
        # return mem[variable_name], "->", mem[variable_name + "'"]

    return do_filter


def print_trace(trace):
    mem_filter = get_mem_filter("$in")
    print('\n\n')
    for tup in trace:
        mem = tup[2]
        print(tup[1], "::", mem_filter(mem))
    print('\n\n')


def evaluate_as_boolean(value):
    if isinstance(value, list) and len(value) > 0 and value[0] == EOF:
        return False
    return not not value


def list_all_files(base_dir):
    return list(map(lambda p: os.path.join(base_dir, p), os.listdir(base_dir)))
