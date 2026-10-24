# DAMN

[简体中文](README.md) | [English](README.en.md)

[Project website](https://lingxi-uwu.github.io/DAMN/) · [English website](https://lingxi-uwu.github.io/DAMN/en.html)

A Minecraft mod dependency network and modpack static analysis tool.

This is the **0.5.6 partially published source edition**, intended for learning, inspection and noncommercial modification. It is an independently runnable source directory and does not include every implementation from the full application. AI tools were used to write and modify code; the project owner provides requirements, design choices, testing feedback and publication decisions. The project is not presented as entirely human-written software.

## What it does

- Reads local instance / mods directories, ZIP archives and MRPACK files.
- Shows mod lists, dependencies declared by files, and static check results.
- Visualizes dependency networks and helps review prerequisite candidates and file identity.
- Looks up online metadata and supports a user-configured Chat Completions-compatible AI service.
- Provides a built-in demonstration with six fictional items. It contains no real modpack or author-machine paths.

Static findings must be checked against the actual game version, loader and runtime. They do not represent a successful launch test. Filename inference, platform information and AI associations are distinguished from file declarations.

## Quick start

Python 3.11 or newer is required. Browser mode uses the Python standard library and needs no third-party Python packages.

Open a terminal in the source directory and run:

```text
python -X utf8 server.py
```

On Windows, you can also double-click start-DAMN.cmd. The application opens a loopback page; close the terminal to stop it. The default port is 8768, with another available port used if it is occupied by another program. The server listens only on 127.0.0.1 and is not a ready-to-deploy public web service.

For the optional Windows desktop window:

```text
python -m pip install -r requirements-desktop.txt
python -X utf8 desktop.py
```

Desktop mode also requires Microsoft Edge WebView2 Runtime. This source edition does not bundle Python, WebView2 or a precompiled EXE. More information: [running instructions](docs/RUNNING.md) (Chinese).

## Settings and data

The public edition defaults to %LOCALAPPDATA%/DAMN-Public/.damn-public-user, separate from the full application's configuration. Use DAMN_PUBLIC_DATA_DIR or --data-dir for another development data directory.

No API Key is included. AI is optional: supply your own endpoint, model and key, and check the provider's charges. Saving settings does not itself start AI analysis. **Online enrichment is enabled by default and can be disabled in Settings → Online information.** It may send mod names, file hashes and platform identifiers. When a working AI service is configured, enrichment may also invoke it and send the relevant evidence and analysis context.

On Windows, keys are protected using the current user's DPAPI. On other systems, keys are retained only for the current session. Do not commit local configurations, keys, caches or actual scan reports.

Project-level CurseForge integration remains subject to API access approval and further implementation review. Publishing interface code is not a claim of official approval or endorsement.

## Published scope

The public edition retains ordinary mod analysis, online metadata adapters, the AI interface, the desktop host, UI and relevant tests.

- Appearance is fixed to the default forest-green theme.
- Private themes, unlock rules, easter eggs, sponsor activation, device binding, signing tools and private keys are excluded. Related backend placeholders explicitly report unavailability.
- Official update and notification services are excluded. The update screen saves local preferences only; checking and installation are unavailable.
- Companion characters, historical user settings, real reports, build caches and old binary packages are excluded.
- Public category data is independently based on official Modrinth categories and uses a flat structure. The earlier screenshot-derived hierarchy and CurseForge numeric mapping are not included.

See [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json), [source and third-party notices](THIRD-PARTY-NOTICES.md), and [publication status](PUBLICATION-STATUS.txt). The website and this English README accompany the source; the application version remains 0.5.6.

## Development checks

Version metadata comes from app_info.py. Trusted HTML and splash templates resolve __VERSION__ through this shared source.

Static assets are included. After editing their source layers, use Node.js 18 or newer to rebuild and check them:

```text
node tools/assemble.mjs
node tools/assemble.mjs --check
python -B -X utf8 -m unittest discover -s . -p "test_*.py"
node tools/check-frontend.mjs
```

The browser interface has no npm installation step. Node.js is used for rebuilding and JavaScript / taxonomy cross-checks. Tests use temporary directories, fictional data and mocked services. Live platforms, paid AI services and different desktop environments need separate verification.

## Use and distribution

The project uses the custom [DAMN Source Noncommercial Use and Distribution License 1.0](LICENSE.txt), to the extent the licensor holds the relevant rights. It allows noncommercial learning, modification and free sharing; it grants no commercial-use rights. Distributed derivatives must provide corresponding covered source, start their name with DAMN, add a modification suffix and a clear unofficial label, and keep this edition's default green as the fixed main theme. Read the Chinese license text for the complete conditions; this README is a summary, not a replacement license.

This is **partial source publication under a noncommercial source-visible license**. It is not MIT, GPL or an OSI-approved open-source license. A license does not create copyright that does not otherwise exist and does not override third-party rights.

## Contact

For questions, bugs or intended-use clarification, [open an issue](https://github.com/Lingxi-UwU/DAMN/issues).
