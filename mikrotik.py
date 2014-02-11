from urllib.request import urlopen
import re
import json
import sys

from bs4 import BeautifulSoup


def with_submenu(tag):
    txt = tag.get_text().lower()
    return tag.name == "b" and ("submenu" in txt or "sub-menu" in txt)


def parse_page(page_url):
    response = urlopen(page_url)
    soup = BeautifulSoup(response.read())
    container = soup.find(class_="manual")
    if not container:
        container = soup.find(id="bodyContent")
        if not container:
            raise Exception
    current_submenu = None
    result = []
    for elem in container.children:
        if isinstance(elem, str):
            continue
        # Check for "submenu" declaration
        sm_tags = elem.find_all(with_submenu)
        if sm_tags:
            if len(sm_tags) > 1:
                raise Exception
            code = sm_tags[0].next_sibling.next_sibling
            current_submenu = code.string.strip()
        # Check for tables 
        if elem.get("class") and "styled_table" in elem['class']:
            for row in elem.find_all("tr"):
                headers = row.find_all("th")
                if headers:
                    col1_title = headers[0].get_text().strip().lower()
                    if col1_title != "property":
                        print("Skipping table: {}".format(col1_title))
                        break
                cells = row.find_all("td")
                if not cells:
                    continue
                definition = cells[0].get_text()
                m = re.match(r"^(?P<prop>[^\s]+)\s\((?P<values>[^;]*)(;\s(D|d)efault:\s?(?P<def>.*)|;|)\)$", definition)
                if not m:
                    print("Unable to parse definition: {}".format(definition))
                    continue
                prop = m.group("prop").strip()
                values_raw = m.group("values").split("|")
                if len(values_raw) > 1:
                    values = [v.strip() for v in values_raw]
                else:
                    values = values_raw[0].strip()
                default = m.group("def") if m.group("def") else None
                description = cells[1].get_text().strip()
                result.append({
                    'name': prop,
                    current_submenu: {
                        'values': values,
                        'default': default,
                        'description': description,
                    },
                })
    return result


def get_pages(root, toc_url):
    response = urlopen(root + toc_url)
    soup = BeautifulSoup(response.read())
    tables = soup.find_all(id="shtable")
    toc = {}
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
