import importlib
from  . import data

EXAMPLE_LIST = ["bw_rs_feed.xml", "rki_rs_feed.xml", "dewiki_simple_short.txt"]

def get_example_list():
    """Function to list all available examples."""
    print(EXAMPLE_LIST)


def get_example(example: str) -> str:
    """Function to load example data."""
    try:
        return importlib.resources.read_text(data, example)
    except FileNotFoundError:
        print("Not an example, use `get_example_list` to see available data.")