from urllib.request import urlopen
import re
import json
import sys
from collections import OrderedDict

from bs4 import BeautifulSoup


def with_command(tag):
    tokens = ["submenu", "sub-menu", "command"]
    txt = tag.get_text().lower()
    return any(token in txt for token in tokens)


def with_readonly(tag):
    tokens = ["readonly", "read-only", "read only"]
    txt = tag.get_text().lower()
    return any(token in txt for token in tokens)


def parse_page(page_url):
    response = urlopen(page_url)
    soup = BeautifulSoup(response.read(), "html5lib")
    container = soup.find(class_="manual")
    if not container:
        container = soup.find(id="bodyContent")
    else:
        # TODO
        pass
    result = []
    current_commands = None
    read_only = False
    def_regexp = re.compile(r"""
        ^(?P<prop>[^\s]+)
        \s\(
        (?P<values>[^;]*)
        (;\s(D|d)efault:\s?(?P<default>.*)|;|)
        \)$
        """, re.X)
    for elem in container.children:
        # Skip regular strings and tocs
        if isinstance(elem, str) or elem.get('id') == "toc":
            continue
        # Look for tables
        if elem.get("class") and "styled_table" in elem['class']:
            # Analyze table headers
            headers = elem.find_all("th")
            if not headers:
                print("Found table without headers, skipping")
                continue
            else:
                col1_title = headers[0].get_text().strip().lower()
                if col1_title != "property":
                    print("Found table with header: {}, skipping".format(col1_title))
                    continue
                print("Found property table")
            if current_commands is None:
                print("Current commands is undefined, skipping")
                continue
            # Analyze rows
            for row in elem.find_all("tr"):
                cells = row.find_all("td")
                if not cells:
                    continue
                definition = cells[0].get_text()
                m = def_regexp.match(definition)
                if not m:
                    print("Unable to parse definition: {}".format(definition))
                    continue
                prop = m.group("prop").strip()
                if read_only:
                    # ???
                    values, default = None, None
                else:
                    values_raw = m.group("values").split("|")
                    if len(values_raw) > 1:
                        values = [v.strip() for v in values_raw]
                    else:
                        values = values_raw[0].strip() or None
                    default = m.group("default") or None
                    # ???
                    #if not isinstance(values, list) and default is not None:
                    #    print("Default is not None: {}".format(definition))
                description = cells[1].get_text().strip()
                for command in current_commands:
                    result.append({
                        'name': prop,
                        'command': command,
                        'info': {
                            'values': values,
                            'default': default,
                            'description': description,
                        },
                    })
            # Reset read-only flag
            read_only = False
            # Skip other checks
            continue
        # Look for "submenu" declaration
        if with_command(elem) or elem.find(with_command):
            codes = [code.string for code in elem.find_all("code")
                if code.string and code.string.startswith("/")]
            if not codes:
                continue
            elif len(codes) > 1:
                print("Miltiple code tags")
            current_commands = [comm.strip() for comm in codes[0].split(",")]
            print("Found commands: {0}".format(current_commands))
        # Look for "read-only" mark
        if with_readonly(elem) or elem.find(with_readonly):
            read_only = True
            print("Found 'read-only' mark")
    return result


def get_pages(root, toc_url):
    response = urlopen(root + toc_url)
    soup = BeautifulSoup(response.read())
    tables = soup.find_all(id="shtable")
    toc = OrderedDict()
    for table in tables:
        rows = table.find_all("tr")
        cells = zip(rows[0].find_all("td"), rows[1].find_all("td"))
        for head, lst in cells:
            # Menus
            menu = head.get_text().strip()
            if not menu:
                continue
            toc[menu] = []
            # Pages
            for li in lst.find_all("li"):
                link = root + li.a["href"]
                toc[menu].append(link)
    return toc


def parse_wiki():
    toc = get_pages("http://wiki.mikrotik.com", "/wiki/Manual:TOC_by_Menu")
    results = {}
    for menu, pages in toc.items():
        print("Processing: {}".format(menu))
        for page in pages:
            print("Processing: {}".format(page))
            for propdef in parse_page(page):
                prop = propdef.pop('name')
                if prop not in results:
                    results[prop] = {}
                results[prop].update(propdef)
    output = [{'name': prop, 'references': refs} for prop, refs in results.items()]
    return output


if __name__ == "__main__":
    with open(sys.argv[1], "w") as f:
        json.dump(parse_wiki(), f)
