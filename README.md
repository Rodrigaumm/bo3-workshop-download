# bo3-workshop-download
Automation of BO3 mod/map download and sending to Telegram.
This automation is focused on Windows and requires [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD#Windows), Winrar and Python 3.10+ to run.

# Demo
[Youtube Demo](https://www.youtube.com/watch?v=Cmke0-NC7fU)

# Usage
- `git clone` this repo
- move `bo3_workshop_download.py` and `requirements.txt` to your [steamcmd](https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip) folder
- open `powershell` on the steamcmd folder
- run `python -m venv .venv`
- run `./.venv/Scripts/Activate.ps1`
- run `pip install -r requirements.txt`
- you can run the script with `python bo3_workshop_download.py`

# Demo gif
![bo3_workshop_download.py demo](https://i.imgur.com/HrRPKVg.gif)