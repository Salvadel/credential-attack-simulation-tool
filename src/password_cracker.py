#!/usr/bin/env python3
"""
------------------------------------------------------------
password_cracker.py - command-line front end

Program Author:             Salvatore DeLuca
Current Version Date:       09/03/2026

For each password you enter, estimates how quickly it could be
cracked by a dictionary attack against a wordlist, falling back to
a full brute-force search if the dictionary attack fails.

Shared attack logic lives in password_cracker_core.py so this file
and password_cracker_gui.py stay in sync. Keep both files in the
same folder.
------------------------------------------------------------
"""

from __future__ import annotations

import sys
from pathlib import Path

from password_cracker_core import (
    DEFAULT_DICTIONARY_PATH,
    PasswordInfo,
    run_attack,
    validate_password,
)


def prompt_for_count() -> int:
    while True:
        raw = input("\nEnter how many passwords you would like to crack: ").strip()
        try:
            n = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if 1 <= n <= 100:
            return n
        print("Please enter a size between 1 and 100.")


def prompt_for_passwords(count: int) -> list[PasswordInfo]:
    passwords: list[PasswordInfo] = []
    for i in range(1, count + 1):
        while True:
            pw = input(f"\nEnter password {i} to crack: ").strip()
            if validate_password(pw):
                passwords.append(PasswordInfo(password=pw))
                break
            print(
                "A character you entered is not allowed (or the password was "
                "empty). Allowed characters are letters, digits, and !@#$*_"
            )
    return passwords


def prompt_dictionary_path() -> Path:
    raw = input(f"\nPath to wordlist [default: {DEFAULT_DICTIONARY_PATH}]: ").strip()
    return Path(raw) if raw else DEFAULT_DICTIONARY_PATH


def run_once() -> None:
    count = prompt_for_count()
    passwords = prompt_for_passwords(count)
    dictionary_path = prompt_dictionary_path()
    run_attack(passwords, dictionary_path)


def main() -> None:
    while True:
        run_once()
        again = input("\nWould you like to run the program again? (y/n): ").strip().lower()
        if again != "y":
            print("Goodbye!")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting.")
        sys.exit(0)
    except EOFError:
        print("\n\nNo more input available. Exiting.")
        sys.exit(0)