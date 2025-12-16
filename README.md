# Příroda Olomouckého kraje - Kiosk

Museum kiosk application for Vlastivědné muzeum v Olomouci.

## Quick Start

```bash
cd priroda-kiosk
FLASK_APP=server.app ./venv/bin/flask run --host=0.0.0.0 --port=5000
```

Open http://localhost:5000

## Development Mode (auto-reload)

```bash
FLASK_DEBUG=1 FLASK_APP=server.app ./venv/bin/flask run --host=0.0.0.0 --port=5000
```

## Structure

```
priroda-kiosk/
├── server/          # Flask application
├── data/
│   ├── content/
│   │   ├── menu.json
│   │   └── pages/cz/*.json
│   └── galleries/*.json
├── static/          # CSS, JS, images
└── venv/            # Python virtual environment
```

## Requirements

- Python 3.x with venv
- Dependencies installed in `./venv`
