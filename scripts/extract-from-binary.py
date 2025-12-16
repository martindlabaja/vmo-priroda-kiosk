#!/usr/bin/env python3
"""
Extract menu structure and data from MySQL ibdata1 binary file.
This script parses the raw binary data to reconstruct the menu hierarchy.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from collections import defaultdict

# Czech name mappings for URL segments
CZECH_NAMES = {
    # Main sections
    "hlavni-menu": "Hlavní menu",
    "geologie": "Geologie a mineralogie",
    "ziva-priroda": "Živá příroda",
    "chranena-uzemi": "Chráněná území",
    "pouzita-literatura": "Použitá literatura",
    "o-expozici": "O expozici muzea",

    # Geology subsections
    "kras-olomouckeho-kraje": "Kras Olomouckého kraje",
    "mineralogicke-lokality": "Mineralogické lokality",
    "paleontologicke-lokality": "Paleontologické lokality",
    "vseobecna-geologie": "Všeobecná geologie",

    # Districts
    "okres-jesenik": "Okres Jeseník",
    "okres-olomouc": "Okres Olomouc",
    "okres-prerov": "Okres Přerov",
    "okres-sumperk": "Okres Šumperk",
    "okres-bruntal-moravskoslezsky-kraj": "Okres Bruntál",

    # Caves/Locations
    "jeskyne-na-pomezi": "Jeskyně Na Pomezí",
    "javoricske-jeskyne": "Javoříčské jeskyně",
    "mladecske-jeskyne": "Mladečské jeskyně",
    "zkamenely-zamek-s-jeskyni": "Zkamenělý zámek s jeskyní",
    "zbrasovske-aragonitove-jeskyne": "Zbrašovské aragonitové jeskyně",
    "nova-ves-soukenna": "Nová Ves - Soukenná",
    "ostruzna": "Ostružná",
    "vapenna": "Vápenná",
    "velka-kras": "Velká Kraš",
    "zalesi": "Zálesí",
    "hlubocky-marianske-udoli": "Hlubočky - Mariánské údolí",
    "branna": "Branná",
    "jivova": "Jívová",
    "zlata-lipa-u-stare-libave": "Zlatá Lípa u Staré Libavé",

    # Living Nature - Habitats
    "horske-hole": "Horské hole",
    "jehlicnaty-les": "Jehličnatý les",
    "listnaty-les": "Listnatý les",
    "luzni-les": "Lužní les",
    "mesto": "Město",
    "venkov": "Venkov",
    "pole-a-mez": "Pole a mez",
    "opusteny-vapencovy-lom": "Opuštěný vápenový lom",
    "rybnik": "Rybník",
    "vlhka-louka": "Vlhká louka",
    "raseliniste": "Rašeliniště",

    # Categories
    "rostliny": "Rostliny",
    "zivocichove": "Živočichové",
    "houby-a-lisejniky": "Houby a lišejníky",

    # Plants
    "jerab-ptaci": "Jeřáb ptačí",
    "lipnice-sirolista": "Lipnice širolistá",
    "jedle-belokora": "Jedle bělokorá",
    "modrin-opadavy": "Modřín opadavý",
    "smrk-ztepily": "Smrk ztepilý",
    "buk-lesni": "Buk lesní",
    "habr-obecny": "Habr obecný",
    "orlicek-obecny": "Orlíček obecný",
    "chmel-otacivy": "Chmel otáčivý",
    "olse-lepkava": "Olše lepkavá",
    "brectan-popinavy": "Břečťan popínavý",
    "skumpa-orobincova": "Škumpa orobincová",
    "zlatobyl-kanadsky": "Zlatobýl kanadský",
    "koniklec-velkokvety": "Koniklec velkokvětý",
    "macka-ladni": "Mácka ladní",
    "pupava-bezlodyzna": "Pupava bezlodyžná",
    "pupava-obecna": "Pupava obecná",
    "chrpa-modra": "Chrpa modrá",
    "penizek-rolni": "Penízek rolní",
    "ruze-sipkova": "Růže šípková",
    "vratic-obecny": "Vratič obecný",
    "briza-belokora": "Bříza bělokorá",
    "ostrice-rusa": "Ostřice rusá",
    "plonik-obecny": "Ploník obecný",
    "raselinik-krivolisty": "Rašeliník křivolistý",
    "rosnatka-okrouhlolista": "Rosnatka okrouhlolistá",
    "suchopyr-uzkolisty": "Suchopýr úzkolistý",
    "kosatec-zluty": "Kosatec žlutý",
    "orobinec-sirokolisty": "Orobinec širokolistý",
    "rakos-obecny": "Rákos obecný",
    "vrba-krehka": "Vrba křehká",
    "zevar-vzprimeny": "Žebratka vzpřímená",
    "dobromysl-obecna": "Dobromysl obecná",
    "kopr-vonny": "Kopr vonný",
    "levandule-lekarska": "Levandule lékařská",
    "oresak-kralovsky": "Ořešák královský",
    "kakost-lucni": "Kakost luční",
    "kosatec-sibirsky": "Kosatec sibiřský",
    "sitina-rozkladita": "Sítina rozkladitá",

    # Fungi
    "mapovnik-zemepisny": "Mapovník zeměpisný",
    "muchomurka-cervena": "Muchomůrka červená",
    "hadovka-smrduta": "Hadovka smrdutá",
    "smrz-jedly": "Smrž jedlý",

    # Animals - Common
    "babocka-koprivova": "Babočka kopřivová",
    "kobylka-hneda": "Kobylka hnědá",
    "kos-horsky": "Kos horský",
    "linduska-lucni": "Linduška luční",
    "okac-horsky": "Okáč horský",
    "okac-mensi": "Okáč menší",
    "okac-rudopasny": "Okáč rudopásný",
    "oresnik-kropenaty": "Ořešník kropenatý",
    "rehek-domaci": "Rehek domácí",
    "zmije-obecna": "Zmije obecná",
    "cervenka-obecna": "Červenka obecná",
    "hrobarik-obecny": "Hrobařík obecný",
    "klikoroh-devetsilovy": "Klikoroh devětsilový",
    "krahujec-obecny": "Krahujec obecný",
    "krivka-obecna": "Křivka obecná",
    "lelek-lesni": "Lelek lesní",
    "lykozrout-smrkovy": "Lýkožrout smrkový",
    "piloritka-velka": "Pilořitka velká",
    "strevlik-zlatoleskly": "Střevlík zlatolesklý",
    "batolec-duhovy": "Batolec duhový",
    "chrobak-jarni": "Chrobák jarní",
    "chroust-obecny": "Chroust obecný",
    "kuna-lesni": "Kuna lesní",
    "martinac-bukovy": "Martináč bukový",
    "plch-velky": "Plch velký",
    "plsik-liskovy": "Plšík lískový",
    "pustik-obecny": "Puštík obecný",
    "strevlik-vrascity": "Střevlík vrásčitý",
    "veverka-obecna": "Veverka obecná",
    "bobr-evropsky": "Bobr evropský",
    "brhlik-lesni": "Brhlík lesní",
    "drozd-zpevny": "Drozd zpěvný",
    "jason-dymnivkovy": "Jasoň dymnivkový",
    "lejsek-belokrky": "Lejsek bělokrký",
    "motylice-obecna": "Motýlice obecná",
    "rohac-obecny": "Roháč obecný",
    "strakapoud-obecny": "Strakapoud obecný",
    "stuzkonoska-olsova": "Stužkonoska olšová",
    "dlouhozobka-svizelova": "Dlouhozobka svízelová",
    "hrdlicka-zahradni": "Hrdlička zahradní",
    "kos-cerny": "Kos černý",
    "kuna-skalni": "Kuna skalní",
    "masarka-obecna": "Masařka obecná",
    "postolka-obecna": "Poštolka obecná",
    "rorys-obecny": "Rorýs obecný",
    "stenice-domaci": "Štěnice domácí",
    "vroubenka-americka": "Vroubenka americká",
    "zavijec-paprikovy": "Zavíječ paprikový",
    "drvodelka-fialova": "Drvodělka fialová",
    "jesterka-obecna": "Ještěrka obecná",
    "kudlanka-nabozna": "Kudlanka nábožná",
    "otakarek-ovocny": "Otakárek ovocný",
    "slavik-obecny": "Slavík obecný",
    "soumracnik-carkovany": "Soumračník čárkovaný",
    "uzovka-hladka": "Užovka hladká",
    "vrabec-polni": "Vrabec polní",
    "vyr-velky": "Výr velký",
    "zlutasek-cilimnikovy": "Žluťásek čilimníkový",
    "cvrcek-polni": "Cvrček polní",
    "hrabos-polni": "Hraboš polní",
    "kobylka-zelena": "Kobylka zelená",
    "krecek-polni": "Křeček polní",
    "sova-palena": "Sova pálená",
    "strevlik-fialovy": "Střevlík fialový",
    "strnad-obecny": "Strnad obecný",
    "tuhyk-obecny": "Ťuhýk obecný",
    "colek-horsky": "Čolek horský",
    "ohnivacek-modroleskly": "Ohniváček modrolesklý",
    "perletovec-koprivovy": "Perleťovec kopřivový",
    "ruznorozec-boruvkovy": "Různorožec borůvkový",
    "skokan-ostronosy": "Skokan ostronosý",
    "strevlik-hrbolaty": "Střevlík hrbolatý",
    "syc-rousny": "Sýc rousný",
    "tetrivek-obecny": "Tetřívek obecný",
    "bruslarka-rybnicna": "Bruslařka rybniční",
    "jehlanka-valcovita": "Jehlanka válcovitá",
    "kormoran-velky": "Kormorán velký",
    "norek-americky": "Norek americký",
    "ondatra-pizmova": "Ondatra pižmová",
    "potapnik-vroubeny": "Potápník vroubený",
    "racek-chechtavy": "Racek chechtavý",
    "splestule-blativa": "Splešťule bahnivá",
    "vazka-beloritna": "Vážka běloňitná",
    "vazka-cervena": "Vážka červená",
    "volavka-popelava": "Volavka popelavá",
    "znakoplavka-obecna": "Znakoplavka obecná",
    "kachna-domaci": "Kachna domácí",
    "koza-domaci": "Koza domácí",
    "kralik-domaci": "Králík domácí",
    "kur-domaci": "Kur domácí",
    "lisaj-svlaccovy": "Lišaj svlačcový",
    "ovce-domaci": "Ovce domácí",
    "paskovka-kerova": "Páskovka keřová",
    "suchomilka-obecna": "Suchomilka obecná",
    "cejka-chocholata": "Čejka chocholatá",
    "hnedasek-jitrocelovy": "Hnědásek jitrocelový",
    "modrasek-bahenni": "Modrásek bahenní",
    "ohnivacek-cernocarny": "Ohniváček černočárný",
    "perletovec-velky": "Perleťovec velký",
    "spacek-obecny": "Špaček obecný",
    "uzovka-obojkova": "Užovka obojková",
    "vazka-obecna": "Vážka obecná",
    "vretenuska-obecna": "Vřetenuška obecná",
}

# English translations
ENGLISH_NAMES = {
    "hlavni-menu": "Main Menu",
    "geologie": "Geology and Mineralogy",
    "ziva-priroda": "Living Nature",
    "chranena-uzemi": "Protected Areas",
    "pouzita-literatura": "References",
    "o-expozici": "About the Exhibition",

    # Geology
    "kras-olomouckeho-kraje": "Karst of Olomouc Region",
    "mineralogicke-lokality": "Mineralogical Sites",
    "paleontologicke-lokality": "Paleontological Sites",
    "vseobecna-geologie": "General Geology",

    # Habitats
    "horske-hole": "Mountain Clearings",
    "jehlicnaty-les": "Coniferous Forest",
    "listnaty-les": "Deciduous Forest",
    "luzni-les": "Floodplain Forest",
    "mesto": "City",
    "venkov": "Countryside",
    "pole-a-mez": "Field and Border",
    "opusteny-vapencovy-lom": "Abandoned Limestone Quarry",
    "rybnik": "Pond",
    "vlhka-louka": "Wet Meadow",
    "raseliniste": "Peatland",

    # Categories
    "rostliny": "Plants",
    "zivocichove": "Animals",
    "houby-a-lisejniky": "Fungi and Lichens",
}


def get_name(slug, lang='cz'):
    """Get human-readable name for a URL slug."""
    if lang == 'en' and slug in ENGLISH_NAMES:
        return ENGLISH_NAMES[slug]
    if slug in CZECH_NAMES:
        return CZECH_NAMES[slug]
    # Convert slug to title case
    return slug.replace('-', ' ').title()


def extract_urls_from_binary(ibdata_path):
    """Extract menu URLs from MySQL ibdata1 file."""
    result = subprocess.run(
        ['strings', ibdata_path],
        capture_output=True,
        text=True
    )

    urls = set()
    for line in result.stdout.split('\n'):
        if line.startswith('hlavni-menu/'):
            urls.add(line.strip())

    return sorted(urls)


def build_menu_tree(urls):
    """Build hierarchical menu structure from flat URLs."""
    tree = {}

    for url in urls:
        parts = url.split('/')
        current = tree

        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {
                    '_children': {},
                    '_url': '/'.join(parts[:i+1])
                }
            current = current[part]['_children']

    return tree


def tree_to_menu_list(tree, parent_url='', id_counter=None):
    """Convert tree structure to menu list format."""
    if id_counter is None:
        id_counter = {'val': 100}

    items = []

    for key, data in sorted(tree.items()):
        if key.startswith('_'):
            continue

        id_counter['val'] += 1
        item_id = id_counter['val']

        # Remove 'hlavni-menu/' prefix for the URL used in the app
        full_url = data.get('_url', key)
        if full_url.startswith('hlavni-menu/'):
            app_url = full_url[12:]  # Remove 'hlavni-menu/' prefix
        else:
            app_url = full_url

        item = {
            'id': item_id,
            'name': get_name(key, 'cz'),
            'name_en': get_name(key, 'en'),
            'url': app_url,
            'url_en': app_url,  # Same structure, content in JSON is per-language
        }

        children = data.get('_children', {})
        if children:
            item['children'] = tree_to_menu_list(children, app_url, id_counter)

        items.append(item)

    return items


def build_indexes(root_items, by_id=None, by_url=None):
    """Build by_id and by_url indexes."""
    if by_id is None:
        by_id = {}
    if by_url is None:
        by_url = {}

    for item in root_items:
        by_id[str(item['id'])] = item
        by_url[item['url']] = item
        if item.get('url_en') and item['url_en'] != item['url']:
            by_url[item['url_en']] = item

        if item.get('children'):
            build_indexes(item['children'], by_id, by_url)

    return by_id, by_url


def main():
    base_dir = Path(__file__).parent.parent
    ibdata_path = base_dir.parent / 'extracted-data/wamp/bin/mysql/mysql5.5.16/data/ibdata1'
    output_dir = base_dir / 'data'

    print(f"Extracting data from: {ibdata_path}")

    # Extract URLs from binary
    urls = extract_urls_from_binary(str(ibdata_path))
    print(f"Found {len(urls)} menu URLs")

    # Build tree structure
    tree = build_menu_tree(urls)

    # Convert to menu list - start from hlavni-menu children
    hlavni_menu = tree.get('hlavni-menu', {}).get('_children', {})
    root_items = tree_to_menu_list(hlavni_menu)

    # Build indexes
    by_id, by_url = build_indexes(root_items)

    menu_data = {
        'root': root_items,
        'by_id': by_id,
        'by_url': by_url
    }

    # Write menu.json
    menu_path = output_dir / 'content' / 'menu.json'
    menu_path.parent.mkdir(parents=True, exist_ok=True)

    with open(menu_path, 'w', encoding='utf-8') as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=2)

    print(f"Written: {menu_path}")

    # Create page JSON files for each menu item
    pages_cz_dir = output_dir / 'content' / 'pages' / 'cz'
    pages_en_dir = output_dir / 'content' / 'pages' / 'en'
    pages_cz_dir.mkdir(parents=True, exist_ok=True)
    pages_en_dir.mkdir(parents=True, exist_ok=True)

    def create_pages(items, parent_type=None):
        for item in items:
            url = item['url']
            safe_filename = url.replace('/', '_') + '.json'

            # Determine page type
            page_type = 'text-page'
            if 'ziva-priroda' in url and url.count('/') == 0:
                page_type = 'tile-section'
            elif 'ziva-priroda' in url and url.count('/') == 1:
                page_type = 'tile-section'

            # Czech page
            page_cz = {
                'id': item['id'],
                'title': item['name'],
                'url': url,
                'type': page_type,
                'description': f"<p>{item['name']} - obsah se připravuje.</p>",
                'image': True
            }

            with open(pages_cz_dir / safe_filename, 'w', encoding='utf-8') as f:
                json.dump(page_cz, f, ensure_ascii=False, indent=2)

            # English page
            page_en = {
                'id': item['id'],
                'title': item['name_en'],
                'url': url,
                'type': page_type,
                'description': f"<p>{item['name_en']} - content is being prepared.</p>",
                'image': True
            }

            with open(pages_en_dir / safe_filename, 'w', encoding='utf-8') as f:
                json.dump(page_en, f, ensure_ascii=False, indent=2)

            if item.get('children'):
                create_pages(item['children'], page_type)

    create_pages(root_items)
    print(f"Created page files in {pages_cz_dir} and {pages_en_dir}")

    # Summary
    print("\n=== Summary ===")
    print(f"Total menu items: {len(by_id)}")
    print(f"Root categories: {len(root_items)}")
    for item in root_items:
        children_count = len(item.get('children', []))
        print(f"  - {item['name']}: {children_count} children")


if __name__ == '__main__':
    main()
