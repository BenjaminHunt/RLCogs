# Configuration Instructions (Windows)

This set of instructions informs developers how to configure their dev environment for Red in VS Code. This process will enable devs to run redbot instances from their shell and should resolve any redbot import references.

1. Install virtual Environment: `pip install virtualenv`
- virtual environment version can be viewed with `virtualenv --version`
1. Create virtual Environment: `python -m venv .venv`
1. At the bottom right of the IDE, a prompt should appear: https://i.stack.imgur.com/HzSHk.png.

    - _We noticed a new virtual environment has been created. Do you want to select it for the workspace folder?_
    - Select **Yes**.

1. Install the project using: `pip install -e .[style]`

    - Notes:
        - `.[style]` is a literal value
        - `.[dev]` or `.[style]` may be used


1. Install Red in accordance with their [official documentation](https://docs.discord.red/en/stable/install_guides/windows.html#installing-red).

1. Enter Virtual Environment with `$ c:/Users/<path_to_project>/.venv/Scripts/Activate.ps1`

# Debugging
1. Open the debug window in VSC (Ctrl+Shift+D) and click the cog.
1. Update `.venv/launch.json` to include the following as a configuration:
```json
{
    "name": "Python: RedBot",
    "type": "python",
    "request": "launch",
    "module": "redbot",
    "args": [
        "DEFAULT",
        "--dev",
        "--debug"
    ],
    "console": "externalTerminal"
}
```
1. replace `DEFAULT` with your instance name

# More Shell Commands
- `redbot --list` lists all redbot instances
- `redbot <instance>` launches a redbot instance
