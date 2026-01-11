import os, sys

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(script_path)

import utils.python_utils as utils
import pprint
import argparse
import inspect

from pymilvus import MilvusClient

db_dir = "/mnt/nvme1n1/rag_bench/db"
db_name = "milvus.db"
history_file_dir = script_dir


def construct_db_filepath(dir, name):
    if dir is None:
        dir = db_dir
    if name is None:
        name = db_name
    return os.path.join(dir, name)


parser = argparse.ArgumentParser(
    prog=script_name, description="Interactive Milvus client for inspect db status"
)
parser.add_argument("-p", "--path")

saved_local_names = set()
saved_local_names = set(locals().keys())
# define all helper functions BELOW this line


def help():
    """Print predefined helper methods and their descriptions"""
    max_local_def_strlen = max((len(local_def) for local_def in local_defs), default=0)
    for local_def in local_defs:
        func_obj = saved_locals[local_def]
        docstring = "" if func_obj.__doc__ is None else func_obj.__doc__
        docstring = os.linesep.join(
            [line for line in docstring.splitlines() if len(line.strip()) > 0]
        )
        signature = inspect.signature(func_obj)
        print(f"{local_def}{signature}: {docstring}")


def ls():
    """List all collection and #rows contained"""
    collections = mc.list_collections()
    max_collection_strlen = max((len(collection) for collection in collections), default=0)
    print(f"total {len(collections)}")
    for collection in collections:
        stats = mc.get_collection_stats(collection)
        print(f"""{collection:{max_collection_strlen}s} {stats["row_count"]}""")


def stat(name: str):
    """
    Get collection properties

    @param name: name of the collection
    """
    if name not in mc.list_collections():
        print(f"\"{name}\" is not a valid collection name")
        return
    print(f"Property:")
    pprint.pprint(mc.describe_collection(name))


def reload_db(dir=None, name=None):
    """
    Load db from file

    @param dir: directory of db
    @param name: name of db
    """
    # db_path = construct_db_filepath(dir, name)
    # assert os.path.isfile(db_path), f"\"{db_path}\" is not a valid db file"
    # mc = MilvusClient(db_path)
    # print(f"Using MilvusClient with db \"{db_path}\"")
    mc = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
    return mc


# define all helper functions ABOVE this line
local_defs = set(locals().keys()) - saved_local_names
saved_locals = locals()

# load/initialize db
mc = reload_db()

title = "MilvusClient is in the variable named \"mc\", entering interactive mode"
exitmsg = "Exiting interactive mode"
try:
    from ptpython.repl import embed
except ImportError:
    history_file = os.path.join(os.path.join(history_file_dir, ".python_history"))

    # start interactive shell
    import code
    import readline
    import rlcompleter

    sys.ps1 = "(mc) >>> "
    sys.ps2 = "(mc) ... "
    vars = globals() | locals()
    readline.set_completer(rlcompleter.Completer(vars).complete)
    readline.parse_and_bind("tab: complete")

    try:
        readline.read_history_file(history_file)
    except Exception:
        pass

    try:
        code.InteractiveConsole(vars).interact(banner=title, exitmsg=exitmsg)
    finally:
        readline.write_history_file(history_file)
else:
    history_file = os.path.join(os.path.join(history_file_dir, ".ptpython_history"))

    def configure(repl):
        repl.vi_mode = True
        repl.enable_history_search = True
        repl.enable_auto_suggest = True
        repl.confirm_exit = False

    embed(globals(), locals(), configure=configure, title=title, history_filename=history_file)
    print(exitmsg)

import os, sys

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(script_path)

import utils.python_utils as utils
import pprint
import argparse
import inspect

from pymilvus import MilvusClient

db_dir = "/mnt/nvme1n1/rag_bench/db"
db_name = "milvus.db"
history_file_dir = script_dir


def construct_db_filepath(dir, name):
    if dir is None:
        dir = db_dir
    if name is None:
        name = db_name
    return os.path.join(dir, name)


parser = argparse.ArgumentParser(
    prog=script_name, description="Interactive Milvus client for inspect db status"
)
parser.add_argument("-p", "--path")

saved_local_names = set()
saved_local_names = set(locals().keys())
# define all helper functions BELOW this line


def help():
    """Print predefined helper methods and their descriptions"""
    max_local_def_strlen = max((len(local_def) for local_def in local_defs), default=0)
    for local_def in local_defs:
        func_obj = saved_locals[local_def]
        docstring = "" if func_obj.__doc__ is None else func_obj.__doc__
        docstring = os.linesep.join(
            [line for line in docstring.splitlines() if len(line.strip()) > 0]
        )
        signature = inspect.signature(func_obj)
        print(f"{local_def}{signature}: {docstring}")


def ls():
    """List all collection and #rows contained"""
    collections = mc.list_collections()
    max_collection_strlen = max((len(collection) for collection in collections), default=0)
    print(f"total {len(collections)}")
    for collection in collections:
        stats = mc.get_collection_stats(collection)
        print(f"""{collection:{max_collection_strlen}s} {stats["row_count"]}""")


def stat(name: str):
    """
    Get collection properties

    @param name: name of the collection
    """
    if name not in mc.list_collections():
        print(f"\"{name}\" is not a valid collection name")
        return
    print(f"Property:")
    pprint.pprint(mc.describe_collection(name))


def reload_db(dir=None, name=None):
    """
    Load db from file

    @param dir: directory of db
    @param name: name of db
    """
    # db_path = construct_db_filepath(dir, name)
    # assert os.path.isfile(db_path), f"\"{db_path}\" is not a valid db file"
    # mc = MilvusClient(db_path)
    # print(f"Using MilvusClient with db \"{db_path}\"")
    mc = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
    return mc


# define all helper functions ABOVE this line
local_defs = set(locals().keys()) - saved_local_names
saved_locals = locals()

# load/initialize db
mc = reload_db()

title = "MilvusClient is in the variable named \"mc\", entering interactive mode"
exitmsg = "Exiting interactive mode"
try:
    from ptpython.repl import embed
except ImportError:
    history_file = os.path.join(os.path.join(history_file_dir, ".python_history"))

    # start interactive shell
    import code
    import readline
    import rlcompleter

    sys.ps1 = "(mc) >>> "
    sys.ps2 = "(mc) ... "
    vars = globals() | locals()
    readline.set_completer(rlcompleter.Completer(vars).complete)
    readline.parse_and_bind("tab: complete")

    try:
        readline.read_history_file(history_file)
    except Exception:
        pass

    try:
        code.InteractiveConsole(vars).interact(banner=title, exitmsg=exitmsg)
    finally:
        readline.write_history_file(history_file)
else:
    history_file = os.path.join(os.path.join(history_file_dir, ".ptpython_history"))

    def configure(repl):
        repl.vi_mode = True
        repl.enable_history_search = True
        repl.enable_auto_suggest = True
        repl.confirm_exit = False

    embed(globals(), locals(), configure=configure, title=title, history_filename=history_file)
    print(exitmsg)
