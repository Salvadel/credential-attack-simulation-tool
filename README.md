<h1 align="center">Credential Attack Simulation Tool</h1>

<p align="center">
A C-based cybersecurity project that simulates real-world credential attack techniques using dictionary and brute-force password cracking methods.
</p>

## Overview

This project is a command-line password auditing and attack simulation utility written in C.  
It demonstrates how weak passwords can be compromised through:

- Dictionary attacks using the `rockyou.txt` leaked password dataset
- Brute-force attacks using generated character combinations

The tool accepts up to **100 user-provided passwords** (maximum length of 20 characters) and attempts to crack them while measuring:

- Total number of attempts
- Time elapsed
- Attack method used
- Password discovery status

If a password is not found within the dictionary, the program automatically switches to a brute-force engine that generates combinations using:

- Uppercase letters
- Lowercase letters
- Numbers
- Symbols

> Brute-force attempts are limited to passwords up to 8 characters in length due to computational complexity.

## Features

- Dictionary-based password cracking
- Brute-force password generation engine
- Performance timing and statistics
- Multi-password testing support
- Interactive CLI workflow
- Restart functionality for repeated testing
- Uses real leaked credential datasets

## Technologies Used

### Languages
- **C**

### Utilities / Datasets
- **rockyou.txt**
- **Git Large File Storage (LFS)**

## Installation

### Clone with Git LFS

This project uses Git Large File Storage (LFS) for the `rockyou.txt` wordlist.

```bash
git lfs install
git clone https://github.com/Salvadel/credential-attack-simulation-tool.git
```

## Alternative Setup

If Git LFS is not installed:

1. Download the repository manually from GitHub
2. Download the `rockyou.txt` wordlist:
   https://weakpass.com/wordlists/rockyou.txt
3. Replace the existing file located at:

```plaintext
src/directories/rockyou.txt
```

## Program Walkthrough

### Launch the executable and enter the number of passwords to test

<p align="center">
<img src="https://i.imgur.com/WWoWpL8.jpeg" width="80%">
</p>

### Enter the passwords for analysis

<p align="center">
<img src="https://i.imgur.com/Wh1LTc6.jpeg" width="80%">
</p>

### View attack results and statistics

<p align="center">
<img src="https://i.imgur.com/uIfYqxV.jpeg" width="80%">
</p>

### Restart the simulation

<p align="center">
<img src="https://i.imgur.com/tFm73MM.jpeg" width="80%">
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

- Multithreading for faster brute-force attacks
- GPU acceleration
- Hash cracking support
- Password entropy analysis
- Exportable reports
- Linux compatibility
- Custom wordlist support
