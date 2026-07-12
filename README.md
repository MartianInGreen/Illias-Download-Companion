# ILIAS Download Companion

A Firefox extension that updates the ILIAS course in the active tab with
[PFERD](https://github.com/Garmelon/PFERD). Firefox communicates with a small
local Python host through Native Messaging; no local server is opened.

## Features

- Update the current ILIAS course with one click
- KIT and generic ILIAS support
- Separate local directory for every course
- File count, start time, duration, and last-update status in the popup
- Persistent `RUN`, `OK`, or `!` toolbar badge and completion notifications
- Secure credential-file or system-keyring authentication
- `courses.toml` inventory in each course-library root
- PFERD process-group termination and reaping after failures or timeouts

## Requirements

- Firefox 109 or newer
- Python 3.11 or newer
- Linux or macOS
- PFERD 3.9 or newer; the installer can install it with `pip`

## Setup

Clone the project into a permanent location and run the setup wizard:

```sh
git clone https://github.com/MartianInGreen/Illias-Download-Companion.git
cd Illias-Download-Companion
python3 companion/install.py
```

The wizard:

- Finds or installs PFERD
- Configures one or more ILIAS installations
- Configures download directories and conflict handling
- Creates a protected credential file or configures the system keyring
- Writes `~/.config/ilias-download-companion/config.json`
- Installs the Firefox native messaging manifest

Existing configuration is not replaced without confirmation. To refresh only
the native manifest, run:

```sh
python3 companion/install.py --manifest-only
```

### Load the extension

For development or local testing:

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on**.
3. Select `extension/manifest.json`.

Temporary add-ons disappear when Firefox exits. For permanent use, zip the
contents of `extension/`, request unlisted signing through
[Mozilla Add-ons](https://addons.mozilla.org/developers/), and install the
signed `.xpi`. Keep the extension ID `ilias-download-companion@local` because
the native host permits only that ID.

Restart Firefox after running the installer or changing native-host settings.

## Usage

1. Open an ILIAS course.
2. Click the extension icon.
3. Click **Update local copy**.

The popup may be closed while PFERD runs. The toolbar badge shows `RUN`, `OK`,
or `!`, and Firefox sends a notification when the update finishes. Reopening
the popup restores the active or latest status and shows:

- Number of saved files
- Date added
- Last successful update
- Current start time and elapsed duration
- PFERD errors from the latest failed run

Only one update runs at a time.

## Authentication

The setup wizard recommends a credential file because Native Messaging cannot
answer an interactive password or 2FA prompt. It securely creates:

```text
~/.config/ilias-download-companion/credentials/PROFILE.txt
```

The file uses PFERD's required format and permission mode `0600`:

```text
username=YOUR_USERNAME
password=YOUR_PASSWORD
```

The password is never placed in `config.json` or printed by the installer.

If you choose the system keyring instead, run the equivalent PFERD command once
in a terminal. It must run a second time without requesting a password before
the extension can use it. Messages such as `GetPassWarning` or `EOFError` mean
PFERD tried to prompt without a terminal.

## Files and configuration

The generated configuration is stored at:

```text
~/.config/ilias-download-companion/config.json
```

Set `ILIAS_COMPANION_CONFIG` before starting Firefox to use another path.
`companion/config.example.json` contains a complete example.

Each profile's `outputDir` is a course-library root. The companion creates a
stable subdirectory for every course and maintains `courses.toml` at the root:

```text
Study/
|-- courses.toml
|-- Linear-Algebra-a1b2c3d4e5/
`-- Operating-Systems-f6e7d8c9b0/
```

`courses.toml` records course names, URLs, directories, dates added, attempts,
successful crawls, file counts, statuses, and errors. It is managed
automatically.

Existing files directly inside `outputDir` from older versions are not moved.

## Troubleshooting

**Could not contact the local companion**

```sh
python3 companion/install.py --manifest-only
```

Restart Firefox and ensure the project has not moved. Flatpak or Snap Firefox
packages may restrict Native Messaging; use Mozilla's or your distribution's
regular Firefox package if necessary.

**No profile allows this origin**

Rerun the installer and configure the exact HTTPS origin from the course URL.
The origin must not contain paths such as `/ilias` or `/login.php`; those belong
in the generic ILIAS `baseUrl`.

**PFERD asks for a password**

Rerun the installer and choose credential-file authentication, or initialize
the selected keyring by running PFERD in a terminal.

**PFERD executable not found**

Rerun the installer. It can install PFERD or save an absolute executable path.

**Update failed**

The popup and `courses.toml` retain the error. PFERD runs in its own process
group; on timeout or interruption, the companion terminates its children,
closes its pipes, and reaps it before reporting the failure.

## Development

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
python3 -m compileall companion tests
node --check extension/background.js
node --check extension/popup.js
```

The extension uses Manifest V2 because a persistent background process is
needed to retain status for long-running PFERD operations.

## Security

- Only configured HTTPS origins are accepted.
- PFERD is launched without shell interpretation.
- Credential files are owner-readable only.
- Browser cookies and page contents are not sent to the companion.
- The native host is restricted to the extension's fixed Firefox ID.
