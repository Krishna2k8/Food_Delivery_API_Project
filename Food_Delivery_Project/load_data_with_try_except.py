"""
load_data_with_try_except.py  -  the SECOND version of load_data
=================================================================
This file is NOT part of the running program and main.py does not import it.
It is a ready-made replacement for ONE function, for after the class on
exception handling (guideline Section 3, point 10, and step 13).

HOW TO USE IT
    1. Open main.py and go to SECTION 2 - STORAGE.
    2. Delete the whole old function  def load_data(path, starter): ...
       (from the line "def load_data" down to "return json.load(file)").
    3. Paste the TWO functions below in its place (starter_copy and load_data).
       Nothing else in main.py changes.
    4. Test it: stop the server, open orders.json, type some rubbish into it,
       save, start the server. The server must start, print a warning, keep
       your broken file as orders.json.damaged, and GET /orders must give [].

WHAT IT DOES WHEN A FILE IS DAMAGED
    * it does not crash
    * it prints what went wrong
    * it renames the bad file to <name>.damaged, so nothing is thrown away
    * it starts again from the starter data
"""


def starter_copy(starter):
    """A fresh copy of the starter list (so the starter itself never changes)."""
    starting_list = []
    for item in starter:
        starting_list.append(dict(item))
    return starting_list


def load_data(path, starter):
    """Read a list from a JSON file. If the file does not exist yet, or it is
    damaged, start again from `starter`. A bad file never crashes the server."""
    if not os.path.exists(path):
        starting_list = starter_copy(starter)
        save_data(path, starting_list)
        return starting_list
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if type(data) is not list:
            raise ValueError("the file does not contain a list")
        return data
    except (ValueError, OSError) as error:
        # ValueError: the text in the file is not good JSON (or not a list).
        # OSError:    the file could not be opened or read at all.
        print("WARNING: could not read " + path + " (" + str(error) + ")")
        print("         The bad file is kept as " + path + ".damaged")
        print("         Starting again from the starter data.")
        os.replace(path, path + ".damaged")
        starting_list = starter_copy(starter)
        save_data(path, starting_list)
        return starting_list
