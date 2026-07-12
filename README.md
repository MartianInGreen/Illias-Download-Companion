# ILIAS Download Companion

A Firefox extension that updates the ILIAS course in the active tab using
[PFERD](https://github.com/Garmelon/PFERD). A small local Python native
messaging host connects Firefox to PFERD; no local web server is opened.

## How it works

1. Open a course in ILIAS.
2. Click the extension and select **Update local copy**.
3. The extension sends the current HTTPS URL to the local companion.
4. The companion finds the profile for that exact origin and runs PFERD.

PFERD updates the existing destination instead of blindly downloading every
file again. The extension badge changes to `OK` or `!` when the run finishes.

## Requirements

- Firefox 109 or newer
- Python 3.11 or newer
- PFERD 3.9 or newer on `PATH`
- Linux or macOS for the included automatic native-host installer

## Complete setup

### 1. Install PFERD

Installing PFERD with `pipx` keeps it isolated while still providing a stable
executable:

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install PFERD
```

Open a new terminal after `ensurepath`, then verify both dependencies:

```sh
python3 --version
pferd --version
command -v pferd
```

Python must be at least 3.11. Keep the path printed by `command -v pferd`; it
is useful if Firefox cannot find PFERD later.

PFERD can alternatively be installed in a virtual environment:

```sh
python3 -m venv ~/.local/share/venvs/pferd
~/.local/share/venvs/pferd/bin/pip install PFERD
```

If `pferd` is not on Firefox's `PATH`, set its absolute path in the companion
config. With the virtual-environment example above, that would be
`"pferd": "/home/alice/.local/share/venvs/pferd/bin/pferd"`.

### 2. Get this project

Clone the repository into a permanent location. Do not move or delete it after
installing the native host because Firefox's native-host manifest contains the
absolute path to `companion/host.py`.

```sh
git clone https://github.com/MartianInGreen/Illias-Download-Companion.git
cd Illias-Download-Companion
```

If you already have the project, run the remaining commands from its root
directory.

### 3. Install the local companion

Install the native messaging manifest for your user:

```sh
python3 companion/install.py
```

This does not require root access. It makes `companion/host.py` executable and
creates the following file:

| Platform | Native messaging manifest |
| --- | --- |
| Linux | `~/.mozilla/native-messaging-hosts/io.github.ilias_download_companion.json` |
| macOS | `~/Library/Application Support/Mozilla/NativeMessagingHosts/io.github.ilias_download_companion.json` |

If the project is moved later, rerun `python3 companion/install.py` from its new
location. The installer overwrites only this project's native-host manifest.

### 4. Create the companion configuration

Create the companion config:

```sh
mkdir -p ~/.config/ilias-download-companion
cp companion/config.example.json ~/.config/ilias-download-companion/config.json
```

On macOS the same path under your home directory is used. Open
`~/.config/ilias-download-companion/config.json` in an editor and replace the
example profiles with your ILIAS installation. Detailed examples are in
[Configuration](#configuration).

At minimum, change:

- `origin` to the scheme and hostname shown in your ILIAS URL, without a path
- `crawler` to `kit-ilias-web` for KIT or `ilias-web` elsewhere
- `outputDir` to the directory in which courses should be stored
- `your-user-name` to your ILIAS username
- `pferd` to the absolute executable path if necessary

The file must remain valid JSON. In particular, JSON does not allow comments or
trailing commas. Validate it with:

```sh
python3 -m json.tool ~/.config/ilias-download-companion/config.json >/dev/null
```

No output means that the JSON is valid.

### 5. Prepare authentication

The companion cannot display an interactive password, browser-login, or 2FA
prompt. PFERD must therefore be able to authenticate non-interactively before
the extension is used.

For a profile using `--keyring`, open any course in Firefox, copy its full URL,
and run the equivalent PFERD command in a terminal. For KIT:

```sh
pferd kit-ilias-web --keyring --username YOUR_USER \
  'https://ilias.studium.kit.edu/goto.php?target=crs_123456' \
  ~/study
```

For a generic ILIAS installation using local login:

```sh
pferd ilias-web \
  --base-url 'https://ilias.example.edu' \
  --client-id 'example-client' \
  --keyring \
  --username YOUR_USER \
  'https://ilias.example.edu/goto.php?target=crs_123456' \
  ~/study
```

Enter credentials and complete any requested login. Run the command a second
time to confirm it succeeds without asking for a password. If it still prompts,
see [Authentication choices](#authentication-choices).

### 6. Load the Firefox extension

For an immediate local test, load it as a temporary add-on:

1. Open `about:debugging#/runtime/this-firefox` in Firefox.
2. Click **Load Temporary Add-on**.
3. Select `extension/manifest.json`.

Firefox lists **ILIAS Download Companion** when loading succeeds. Temporary
add-ons disappear whenever Firefox exits and must then be loaded again.

For permanent use, package the contents of `extension/` and submit the archive
for signing through [Mozilla Add-ons](https://addons.mozilla.org/developers/).
The manifest already contains the fixed ID
`ilias-download-companion@local`, which must not be changed because the native
host allows only that extension ID.

From the project root, a package can be created with:

```sh
mkdir -p build
(cd extension && zip -r ../build/ilias-download-companion.zip .)
```

Upload `build/ilias-download-companion.zip` for unlisted signing. Download the
signed `.xpi`, open `about:addons`, choose **Install Add-on From File** from the
gear menu, and select the `.xpi`. Mozilla account and signing requirements can
change; follow the instructions shown by the Add-ons Developer Hub.

### 7. Perform the first update

1. Open an ILIAS course page whose origin matches a configured profile.
2. Click the extension icon in Firefox's toolbar.
3. Click **Update local copy**.
4. Keep Firefox open while PFERD runs. The popup itself may be closed.
5. Wait for an `OK` badge, then inspect the configured `outputDir`.

The extension passes the active course URL and tab title to the companion. The
companion creates a stable course directory below `outputDir`; subsequent
clicks synchronize that copy. The popup shows the number of files currently in
that directory, when the course was added, and the last successful crawl.

The companion also creates `courses.toml` at the root of `outputDir`. This is a
human-readable inventory of every saved course, including its URL, directory,
added date, last attempt, last successful crawl, file count, status, and latest
error. It is managed automatically and should not be edited while an update is
running.

## Configuration

The default path is
`~/.config/ilias-download-companion/config.json`. Set
`ILIAS_COMPANION_CONFIG` in Firefox's environment to override it.

```json
{
  "pferd": "pferd",
  "timeoutSeconds": 3600,
  "profiles": [
    {
      "name": "KIT ILIAS",
      "origin": "https://ilias.studium.kit.edu",
      "crawler": "kit-ilias-web",
      "outputDir": "~/study",
      "options": [
        "--keyring",
        "--username",
        "your-user-name",
        "--on-conflict",
        "no-delete"
      ]
    }
  ]
}
```

Each profile supports:

| Field | Meaning |
| --- | --- |
| `name` | Name shown after an update |
| `origin` | Exact HTTPS origin allowed for this profile |
| `crawler` | `kit-ilias-web` or `ilias-web` |
| `outputDir` | Course-library root containing one directory per course and `courses.toml` |
| `baseUrl` | Generic ILIAS base URL; defaults to `origin` |
| `clientId` | Client ID for a generic local-login ILIAS installation |
| `options` | Allowlisted PFERD crawler options and their values |

`origin` matching is exact. A profile for `https://ilias.example.edu` does not
allow `http://ilias.example.edu`, `https://login.example.edu`, or any other
subdomain. Add a separate profile if an installation is legitimately available
through multiple origins.

Multiple universities can be configured in the same file:

```json
{
  "pferd": "/home/alice/.local/bin/pferd",
  "timeoutSeconds": 3600,
  "profiles": [
    {
      "name": "KIT",
      "origin": "https://ilias.studium.kit.edu",
      "crawler": "kit-ilias-web",
      "outputDir": "/home/alice/Study/KIT",
      "options": ["--keyring", "--username", "uxxxx", "--on-conflict", "no-delete"]
    },
    {
      "name": "Example University",
      "origin": "https://ilias.example.edu",
      "crawler": "ilias-web",
      "baseUrl": "https://ilias.example.edu",
      "clientId": "example-client",
      "outputDir": "/home/alice/Study/Example",
      "options": ["--keyring", "--username", "alice", "--on-conflict", "no-delete"]
    }
  ]
}
```

Use absolute output paths when possible. `~` is expanded by the companion, but
environment variables such as `$HOME` are not expanded.

Earlier versions of the companion passed `outputDir` directly to PFERD. The
current version creates one subdirectory per course so different courses cannot
overwrite each other. Existing files directly inside `outputDir` are left in
place and are not moved automatically.

### Finding generic ILIAS settings

For installations other than KIT, PFERD needs the generic `ilias-web` crawler.
The `origin` and `baseUrl` are usually the beginning of the login URL. For
example, given:

```text
https://ilias.example.edu/login.php?client_id=Example&cmd=force_login
```

use:

```json
"origin": "https://ilias.example.edu",
"baseUrl": "https://ilias.example.edu",
"clientId": "Example"
```

Some installations include a path in their base URL, such as
`https://example.edu/ilias`. Keep that path in `baseUrl`, but keep `origin` as
only `https://example.edu`. PFERD's current list of known installations and
login details is in its
[configuration documentation](https://github.com/Garmelon/PFERD/blob/master/CONFIG.md#the-ilias-web-crawler).

### Authentication choices

The companion accepts common safe crawler options such as `--keyring`,
`--username`, `--credential-file`, `--on-conflict`, `--redownload`, `--links`,
`--videos`, `--forums`, `--tasks`, and `--task-delay`. Arguments are passed
directly to PFERD without shell interpretation.

Native hosts cannot answer an interactive password or two-factor prompt. The
recommended setup is PFERD's system keyring:

1. Configure the profile with `--keyring` and `--username`.
2. Run the equivalent command once in a terminal so PFERD can ask for and save
   the password, for example:

```sh
pferd kit-ilias-web --keyring --username YOUR_USER \
  https://ilias.studium.kit.edu/goto.php?target=crs_123456 \
  ~/study
```

After the keyring is populated, extension-triggered runs are non-interactive.
A credential file also works, but it contains a plaintext password and should
be readable only by its owner (`chmod 600`). Shibboleth flows or fresh 2FA
prompts may still require an interactive PFERD run.

To use a credential file, create it with exactly two lines:

```text
username=YOUR_USER
password=YOUR_PASSWORD
```

Then protect it and reference it from the profile:

```sh
chmod 600 ~/.config/pferd/credentials
```

```json
"options": [
  "--credential-file",
  "/home/alice/.config/pferd/credentials",
  "--on-conflict",
  "no-delete"
]
```

Do not combine `--credential-file` with `--keyring` or `--username`. Prefer the
keyring whenever the ILIAS login method supports it.

### Conflict behavior

PFERD's default conflict mode may ask questions, which does not work from the
extension. Every profile should explicitly use a non-interactive mode:

- `--on-conflict no-delete` updates remote files but keeps local-only files.
- `--on-conflict remote-first` makes the local copy follow ILIAS, including
  deleting files removed remotely.
- `--on-conflict local-first` preserves local versions when they differ.

`no-delete` is the safest starting point and is used in the examples.

## Updating or uninstalling

After pulling a newer version of this repository, reload the temporary add-on
from `about:debugging`, or rebuild and reinstall the signed `.xpi`. Rerun the
companion installer if `companion/host.py` moved:

```sh
git pull
python3 companion/install.py
```

To uninstall, remove the extension in `about:addons`, then remove the native
manifest and optional configuration:

```sh
rm ~/.mozilla/native-messaging-hosts/io.github.ilias_download_companion.json
rm -r ~/.config/ilias-download-companion
```

On macOS, remove the native manifest from
`~/Library/Application Support/Mozilla/NativeMessagingHosts/` instead. Removing
the companion configuration does not delete downloaded courses.

## Troubleshooting

### Could not contact the local companion

Rerun the installer and restart Firefox completely:

```sh
python3 companion/install.py
```

Check that the generated manifest exists and that its `path` points to the
current `companion/host.py`. Also check that the extension ID in
`extension/manifest.json` remains `ilias-download-companion@local`.

On Linux, Firefox installed through Flatpak or Snap may be sandboxed away from
the host manifest or executable. Native messaging support varies by package and
distribution. If the manifest is correct but Firefox cannot launch it, try the
Firefox package supplied directly by Mozilla or your distribution.

### Config not found

Create `~/.config/ilias-download-companion/config.json` as described above.
Firefox inherits environment variables only when it starts, so after setting
`ILIAS_COMPANION_CONFIG`, quit all Firefox processes and reopen it.

### No profile allows this origin

Compare the active tab's address with `origin`. It must use HTTPS and match the
hostname and optional port exactly. Do not put `/ilias`, `/login.php`, or any
other path in `origin`; paths belong in `baseUrl`.

### PFERD executable not found

Run `command -v pferd` and copy the resulting absolute path into the top-level
`pferd` setting. Restart Firefox after changing how PFERD is installed.

### PFERD exits with an error or waits for input

Copy the course URL and run the equivalent PFERD command in a terminal. This
shows the full error and permits credential or 2FA prompts. Confirm that:

- The username, `baseUrl`, and `clientId` are correct.
- Keyring authentication has been initialized.
- `--on-conflict` is non-interactive.
- The output directory is writable.
- The selected page is an ILIAS course or supported ILIAS element.

The popup displays the last 4,000 characters of PFERD's combined output. For
more detail, reproduce the command in a terminal and add PFERD's `--explain`
global option manually.

### The popup closes while downloading

This is expected and does not stop the update. The background extension owns
the native request. Watch the toolbar badge: `OK` means success and `!` means
the run failed. Only one update can run at a time.

### A failed update leaves PFERD running

The companion starts PFERD in a dedicated process group. On timeout,
interruption, or native-host failure it first terminates that entire group, then
force-kills it if necessary, and waits for the process to be reaped before
reporting the error. A normal nonzero PFERD exit is also reaped. If a PFERD
process remains after the extension reports failure, record the error and the
process details because that indicates a bug.

### A Shibboleth or 2FA login expires

Run the profile's PFERD command manually in a terminal to complete the login.
Once it can run without prompting, trigger the course again from Firefox.

## Security

- Only HTTPS URLs whose exact origin appears in a profile are accepted.
- PFERD is launched as an argument array, never through a shell.
- The native host is available only to the extension's fixed Firefox ID.
- Browser cookies and page contents are not sent to the companion.
- Update output is capped before it is returned to Firefox.

## Development

Run the host unit tests and validate Python syntax:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall companion tests
```

The extension uses Manifest V2 because Firefox's non-persistent Manifest V3
background lifecycle is a poor fit for a long-running native PFERD operation.
