# EVLC — an argument-safe VLC enqueue wrapper

EVLC is a small Windows wrapper that sends media URLs, playlists, and files to
an existing VLC instance without routing the arguments through `cmd.exe`.

It is particularly useful with the cross-browser
[Open in VLC](https://webextension.org/listing/open-in-vlc.html) extension.
The included `evlc-browser.exe` can be selected as the extension's VLC
executable while `evlc.py` handles VLC discovery, argument cleanup, and
playlist enqueueing.

The launcher contains no browser-specific code. It has been tested with
Firefox and is expected to work with Chrome, Edge, Brave, Opera, Vivaldi, and
other supported Chromium-based browsers when the extension and its native
client are installed.

## Why use it?

Media URLs often contain characters such as `&`, `%`, `?`, `=`, and spaces.
Passing them through a batch file or command shell can alter or split the URL.

EVLC launches VLC directly with a structured argument list. It also:

- reuses one VLC instance;
- enqueues new media instead of replacing the current playlist;
- accepts URLs, local files, and playlist files;
- extracts one or more HTTP(S) URLs from pasted text;
- converts the extension's HTTP metadata to VLC item options;
- supports the extension's page-title, referrer, and user-agent arguments;
- uses VLC's localhost RC interface for reliable playlist enqueueing;
- can record received items in `VLC-enqueued.log`;
- supports a dry-run mode for troubleshooting.

## Files

```text
evlc.py
evlc-browser.exe
evlc-browser-launcher/
├── evlc-browser-launcher.csproj
└── Program.cs
tests/
└── test_evlc.py
```

- `evlc.py` contains the wrapper behavior.
- `evlc-browser.exe` is the browser-neutral, windowless extension bridge.
- `evlc-browser-launcher/` contains the C# source used to build the bridge.
- `tests/` contains argument and RC transport regression tests.

The executable is not a modified copy of VLC and does not contain VLC. It
simply starts `evlc.py` while preserving the arguments supplied by the
extension.

## Requirements

- 64-bit Windows (for the supplied executable)
- [VLC media player](https://www.videolan.org/vlc/)
- Python 3.9 or later, including `pythonw.exe`
- [.NET 8 Runtime](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)
- The Open in VLC extension and its native client

By default, the bridge looks for Python installations under:

```text
%LOCALAPPDATA%\Programs\Python
```

It falls back to finding `pythonw.exe` through `PATH`.

## Installation

1. Download or clone this project.
2. Keep `evlc-browser.exe` and `evlc.py` in the same directory.
3. Confirm that VLC, Python 3, and the .NET 8 Runtime are installed.
4. Install
   [Open in VLC](https://webextension.org/listing/open-in-vlc.html) in your
   browser and install its native client.
5. Open the extension's options page.
6. Set **Path to the VLC executable** to the full path of
   `evlc-browser.exe`, for example:

   ```text
   C:\Tools\EVLC\evlc-browser.exe
   ```

## Recommended extension settings

### Custom arguments

Leave the extension's custom-arguments field empty unless you need additional
VLC behavior.

Do not add either of these options:

```text
--one-instance
--playlist-enqueue
```

`evlc.py` already supplies both.

The extension documentation shows `--meta-title=[[title]]` as a custom
argument example, but it is unnecessary when **Send Page Title as VLC
argument** is enabled. Using both sends the title metadata twice. The built-in
checkbox is preferred because the extension places `:meta-title=...` after the
media URL, where VLC expects item-specific metadata.

### One-instance mode

Disable **Open VLC in one instance mode** in the extension.

The wrapper already supplies `--one-instance`. Leaving the checkbox enabled
is normally harmless, but it sends the same option twice.

### Page metadata and HTTP headers

These options can remain enabled:

- **Send Page Title as VLC argument**
- **Use http-referrer argument to send the page as the referrer**
- **Use http-user-agent argument to send requests with the browser
  user-agent string**
- **Use Page Title for M3U8 Tracks**

The extension supplies HTTP metadata before the media item:

```text
--http-referrer
https://example.com/watch?v=123
```

On Windows, VLC 3.x's one-instance handoff only forwards media items and
colon-prefixed input options. EVLC therefore converts the extension arguments
and places them after the media:

```text
C:\Users\Name\AppData\Local\Temp\media-1637503940.m3u8
:http-referrer=https://example.com/watch?v=123
:http-user-agent=Mozilla/5.0 ...
:meta-title=Example
```

This ordering is required for the temporary VLC process to transfer the item
and its metadata to the already-running VLC playlist.

### M3U8 container and temporary files

The extension's **Use M3U8 Container** option can remain enabled. When
multiple media links are selected, the extension combines them into a
temporary playlist and sends that playlist to EVLC.

On Windows, Open in VLC version 0.4.4 creates files similar to:

```text
%TEMP%\media-1637503940.m3u8
```

The extension passes this as a normal Windows path, for example:

```text
C:\Users\Name\AppData\Local\Temp\media-1637503940.m3u8
```

It does not need to convert the path to a `file:///C:/...` URI. VLC accepts
the native Windows form directly, and EVLC preserves it unchanged.

The container option applies when the extension groups multiple selected
media links. Sending an individual detected link can still invoke EVLC with
the media URL directly, so both temporary playlist paths and standalone URLs
may appear in `VLC-enqueued.log`.

The extension does not currently delete these files after opening them.
Depending on the enabled extension options, they may contain media URLs,
temporary access tokens, the source page URL as an HTTP referrer, the browser
user-agent string, and page titles.

These files are created and managed by the extension, not by EVLC. EVLC only
receives the resulting `.m3u8` path, so it cannot safely remove the playlist
while VLC may still be reading it. Users concerned about retention should
periodically clear old `media-*.m3u8` files from `%TEMP%` or disable **Use
M3U8 Container** when it is not needed.

## How it works

The extension starts `evlc-browser.exe` with the media path or URL and its
selected VLC arguments.

The bridge:

1. locates `evlc.py` beside itself;
2. locates `pythonw.exe`;
3. starts the Python wrapper without opening a console window;
4. forwards every argument without shell re-parsing.

On the first launch, the Python wrapper starts VLC in this general form:

```text
vlc.exe --one-instance --playlist-enqueue \
  --extraintf=oldrc --rc-host=127.0.0.1:4212 --rc-quiet \
  [media] [item options]
```

The RC interface listens only on the local loopback address. Later EVLC calls
connect to that port and send VLC's `enqueue` command directly. This avoids a
VLC 3.x issue where its hidden Windows one-instance receiver can disappear
while VLC is still running.

If the RC interface is unavailable, EVLC falls back to launching VLC with its
normal `--one-instance --playlist-enqueue` arguments.

VLC is located in this order:

1. the `VLC_EXE` environment variable;
2. `vlc.exe` available through `PATH`;
3. `C:\Program Files\VideoLAN\VLC\vlc.exe`;
4. `C:\Program Files (x86)\VideoLAN\VLC\vlc.exe`.

## Command-line use

The Python wrapper can also be called directly:

```powershell
python .\evlc.py "https://example.com/video.m3u8"
python .\evlc.py "C:\Media Files\playlist.m3u8"
python .\evlc.py "https://example.com/one" "https://example.com/two"
```

To inspect the generated VLC command without launching VLC:

```powershell
python .\evlc.py --dry-run `
  "--http-referrer" `
  "https://example.com/watch?v=123" `
  "https://cdn.example.com/video.m3u8?token=abc&part=1"
```

## Environment-variable overrides

### Custom VLC location

Set `VLC_EXE` to the full path of VLC:

```powershell
$env:VLC_EXE = "D:\Applications\VLC\vlc.exe"
```

### Custom Python location

Set `EVLC_PYTHONW` to the full path of `pythonw.exe`:

```powershell
$env:EVLC_PYTHONW = "C:\Python312\pythonw.exe"
```

### Custom script location

Normally, `evlc.py` must be beside `evlc-browser.exe`. To keep it elsewhere,
set `EVLC_SCRIPT`:

```powershell
$env:EVLC_SCRIPT = "C:\Tools\EVLC\scripts\evlc.py"
```

Environment variables set only with `$env:...` apply to the current
PowerShell process. Use Windows Environment Variables settings or `setx` if
the extension must see them in future browser sessions.

## Building `evlc-browser.exe`

Install the .NET 8 SDK or a newer compatible SDK, then run from the project
root:

```powershell
dotnet publish `
  .\evlc-browser-launcher\evlc-browser-launcher.csproj `
  -c Release `
  -o .\publish
```

The resulting file is:

```text
publish\evlc-browser.exe
```

Copy it beside `evlc.py`.

The published launcher is a single, framework-dependent executable. Users
therefore need the .NET 8 Runtime, but no additional launcher files.

## Logging and privacy

Logging is enabled by default. Received arguments are appended to:

```text
VLC-enqueued.log
```

The log is created in the same directory as `evlc.py`.

To disable logging, change this setting near the top of `evlc.py`:

```python
LOGGING_ENABLED = False
```

Streaming URLs can contain temporary access tokens or other private values.
The HTTP referrer and user-agent may also be logged. Treat the log as
sensitive and delete or protect it as appropriate.

If the extension's **Use M3U8 Container** option is enabled, also be aware of
the temporary playlist files described under
[M3U8 container and temporary files](#m3u8-container-and-temporary-files).

If the bridge itself cannot find Python or `evlc.py`, it writes details to:

```text
evlc-browser-error.log
```

beside `evlc-browser.exe`.

## Troubleshooting

### Nothing happens when using the extension

Check `evlc-browser-error.log` beside the executable. Confirm that:

- `evlc.py` is beside `evlc-browser.exe`;
- Python 3 and `pythonw.exe` are installed;
- the .NET 8 Runtime is installed;
- the extension's native client is installed;
- the extension points to the full path of `evlc-browser.exe`.

After installing or updating EVLC, fully exit VLC once and start it again
through `evlc.py`, your command-line shortcut, or `evlc-browser.exe`. The first EVLC launch
starts VLC's localhost enqueue listener on port `4212`; a VLC instance that
was already running before the update will not have that listener.

If another application already uses `127.0.0.1:4212`, change `RC_PORT` near
the top of `evlc.py`.

### VLC cannot be found

Install VLC in its normal location or set the `VLC_EXE` environment variable.

### Windows warns about the executable

Locally built and GitHub-hosted executables may be unsigned, so Windows
SmartScreen can display a warning. Build the executable from the included
source if you prefer not to run the supplied binary.

### A comma inside a URL

Commas are preserved, including at the end of a URL. The wrapper only removes
trailing `.`, `;`, and `]` characters when extracting a URL from surrounding
text.

## Open in VLC documentation

The extension's options and custom-argument syntax are documented on its
[support and FAQ page](https://webextension.org/listing/open-in-vlc.html).

## Tests

Run the regression suite from the repository root:

```powershell
python -m unittest discover -s tests -v
```

## License

EVLC is released under the [MIT License](LICENSE).
