<h1 align="center">Credential Attack Simulation Tool</h1>
<p align="center">
A Python-based cybersecurity project that simulates real-world credential attack techniques using dictionary and brute-force password cracking methods — available as both a command-line tool and a desktop GUI application.
</p>

<p align="center">
<img src="../images/gui-main.png" width="80%">
</p>

## Overview

This project is a password auditing and attack simulation utility written in Python.
It demonstrates how weak passwords can be compromised through:

- Dictionary attacks using the `rockyou.txt` leaked password dataset
- Brute-force attacks using generated character combinations

The tool accepts up to **100 user-provided passwords** and attempts to crack them while measuring:

- Total number of attempts
- Time elapsed
- Attack method used
- Password discovery status

If a password is not found within the dictionary, the program automatically switches to a brute-force engine that generates combinations using:

- Uppercase letters
- Lowercase letters
- Numbers
- Symbols

> Brute-force attempts are limited to passwords up to 8 characters in length due to computational complexity. Longer passwords are flagged as too long for brute force rather than attempted.

The project ships two interchangeable front ends built on the same attack logic:

- **`password_cracker.py`** — the original interactive command-line workflow
- **`password_cracker_gui.py`** — a lightweight desktop GUI (built with Python's standard-library `tkinter`, no extra installs required)

Both share `password_cracker_core.py`, so the dictionary attack, brute-force engine, and timing logic behave identically regardless of which interface you use.

## Features

- Dictionary-based password cracking
- Brute-force password generation engine
- Performance timing and statistics
- Multi-password testing support
- Interactive CLI workflow with a restart option for repeated testing
- Desktop GUI with:
  - A live, color-coded activity log (cracked / skipped / error at a glance)
  - A Stop button that safely cancels a running brute-force search mid-attack
  - A confirmation prompt before starting any brute-force search large enough to take a very long time
  - A window that sizes itself to your screen automatically
- Uses real leaked credential datasets
- Wordlist location is auto-detected next to the program — no path to edit, works the same on any machine

## Technologies Used

### Languages
- **Python 3.9+**

### Libraries
- Python standard library only — `tkinter` for the GUI, no third-party packages required

### Utilities / Datasets
- **rockyou.txt**
- **Git Large File Storage (LFS)**

## Installation

### Requirements
- Python 3.9 or newer
- On Linux, the GUI requires the `tkinter` system package, which isn't always bundled by default:
  ```bash
  sudo apt install python3-tk
  ```
  (Windows and macOS installs from python.org include `tkinter` already.)

### Clone with Git LFS
This project uses Git Large File Storage (LFS) for the `rockyou.txt` wordlist.

```bash
git lfs install
git clone https://github.com/Salvadel/credential-attack-simulation-tool.git
```

### Running the tool
```bash
# Command-line version
python3 password_cracker.py

# Desktop GUI version
python3 password_cracker_gui.py
```

`password_cracker_core.py` must stay in the same folder as whichever front end you run — it holds the shared attack logic both interfaces call into.

## Alternative Setup

If Git LFS is not installed:

1. Download the repository manually from GitHub
2. Download the `rockyou.txt` wordlist:
   https://weakpass.com/wordlists/rockyou.txt
3. Place it at:
```plaintext
src/dictionaries/rockyou.txt
```

The program looks for a `dictionaries` folder next to the Python files themselves (not the folder you happen to launch it from), so as long as `rockyou.txt` sits alongside the scripts in that structure, it resolves correctly regardless of how or where you run it from.

## Program Walkthrough

### Command-line interface

#### Launch the program and enter the number of passwords to test
<p align="center">
<img src="../images/cli-launch.png" width="80%">
</p>

#### Enter the passwords for analysis
<p align="center">
<img src="../images/cli-password-entry.png" width="80%">
</p>

#### View attack results and statistics
<p align="center">
<img src="../images/cli-results.png" width="80%">
</p>

### Desktop GUI

#### Main window on launch
<p align="center">
<img src="../images/gui-main.png" width="80%">
</p>

#### Add one or more passwords to test
<p align="center">
<img src="../images/gui-passwords-added.png" width="80%">
</p>

#### Results in the color-coded activity log
<p align="center">
<img src="../images/gui-results.png" width="80%">
</p>

## Educational Purpose

This project was created for educational and cybersecurity research purposes only.
It is intended to demonstrate:

- Password security weaknesses
- Credential attack methodologies
- Brute-force attack limitations
- The importance of strong password practices

Do not use this tool against systems or accounts without explicit authorization.

## Future Improvements

Potential future enhancements include:

- Multiprocessing brute force to use multiple CPU cores for real speed (current threading keeps the GUI responsive, but doesn't parallelize the search itself)
- GPU acceleration
- Hash cracking support (currently compares plaintext, matching the original attack model)
- Password entropy analysis
- Exportable reports
- Standalone packaged executables (e.g. via PyInstaller) so the tool can run without a Python install
- Custom wordlist presets beyond rockyou.txt
