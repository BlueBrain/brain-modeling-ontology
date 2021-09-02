MAPPING = {
    "β": "beta",
    "\xa0": " ",
    "–": "-"
}


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


def remove_non_ascii(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    for k, v in MAPPING.items():
        content = content.replace(k, v)

    if not is_ascii(content):
        for c in content:
            if ord(c) >= 128:
                content = content.replace(c, "")

        with open(filepath, "w") as f:
            f.write(content)
