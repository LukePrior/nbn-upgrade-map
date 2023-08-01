import json


def print_progress_bar(iteration, total, prefix="", suffix="", decimals=1, length=100, fill="█", printEnd="\r"):
    """
    Call in a loop to create terminal progress bar.
    Borrowed from https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()


def write_json_file(filename: str, data: dict, indent=4):
    """Write a dict to a JSON file."""
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=indent)


def read_json_file(filename: str) -> dict:
    """Read a dict from a JSON file."""
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)
