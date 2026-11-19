#!/usr/bin/env python3
"""
------------------------------------------------------------
password_cracker_core.py

Shared attack logic for the password crack-time estimator.
Both password_cracker.py (CLI) and password_cracker_gui.py (GUI)
import from this module, so there is exactly one implementation
of the dictionary attack / brute force logic to keep correct.

This module does not call print()/input() directly - every
front-end supplies its own log/confirm/should_stop callbacks,
which is what lets the same logic run in a terminal or inside a
GUI event loop without changes.
------------------------------------------------------------
"""

from __future__ import annotations

import itertools
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# ---- Configuration -------------------------------------------------

# Matches the original C alphabet: a-z A-Z 0-9 ! @ # $ * _
ALPHABET: str = string.ascii_letters + string.digits + "!@#$*_"

# Anchor the default dictionary path to the folder this script lives in,
# not to the process's current working directory. A plain relative path
# like Path("dictionaries/rockyou.txt") resolves against whatever
# directory the program happened to be *launched* from - fine from a
# terminal already cd'd into the project folder, but it silently breaks
# from a double-click, a shortcut, an IDE run button, or any other
# launch location.
#
# Path(__file__).resolve().parent always points at the folder this .py
# file is actually sitting in, so as long as "dictionaries" sits next to
# the script (same layout as before, alongside where the .c file used to
# be), this resolves correctly regardless of launch method. As a second
# safety net, also check dictionaries/rockyou.txt under the current
# working directory, in case the project is laid out differently than
# expected - first match wins.
SCRIPT_DIR = Path(__file__).resolve().parent


def find_default_dictionary() -> Path:
    script_relative = SCRIPT_DIR / "dictionaries" / "rockyou.txt"
    if script_relative.exists():
        return script_relative

    cwd_relative = Path.cwd() / "dictionaries" / "rockyou.txt"
    if cwd_relative.exists():
        return cwd_relative

    # Neither exists yet - return the script-relative path anyway so the
    # UI has something sensible to display and the "not found" message
    # points at the location that's actually expected to hold it.
    return script_relative


DEFAULT_DICTIONARY_PATH = find_default_dictionary()

MAX_BRUTE_FORCE_LENGTH = 8              # same cap as the original C program
PROGRESS_REPORT_INTERVAL = 2_000_000    # log a progress line every N guesses
LARGE_KEYSPACE_WARNING = 50_000_000     # ask for confirmation above this many guesses


# ---- Data model ------------------------------------------------------

@dataclass
class PasswordInfo:
    password: str
    attempts: int = 0
    time_taken: float = 0.0
    cracked: bool = False
    too_long: bool = False
    skipped: bool = False


def validate_password(password: str) -> bool:
    """True if password is non-empty and every character is in ALPHABET."""
    return len(password) > 0 and all(ch in ALPHABET for ch in password)


def estimate_keyspace(length: int) -> int:
    """All combinations checked from length 1 through the target length."""
    return sum(len(ALPHABET) ** n for n in range(1, length + 1))


# ---- Callback types --------------------------------------------------

LogFn = Callable[[str], None]
ConfirmFn = Callable[[str, int], bool]   # (password, keyspace) -> proceed?
StopFn = Callable[[], bool]              # True if caller asked to cancel


def _default_log(message: str) -> None:
    print(message)


def _default_confirm(password: str, keyspace: int) -> bool:
    print(f"\nBrute forcing '{password}' could take up to {keyspace:,} guesses. "
          "This may take a very long time.")
    answer = input("Continue anyway? (y/n): ").strip().lower()
    return answer == "y"


def _default_stop() -> bool:
    return False


# ---- Dictionary attack -------------------------------------------------

def dictionary_attack(
    passwords: list[PasswordInfo],
    dictionary_path: Path,
    log: LogFn = _default_log,
    should_stop: StopFn = _default_stop,
) -> None:
    """Stream a wordlist once and update every matching test-password entry."""
    # Keep all duplicate entries: a dictionary keyed directly to one PasswordInfo
    # silently lost other entries with the same password.
    remaining: dict[str, list[PasswordInfo]] = {}
    for info in passwords:
        if not info.cracked:
            remaining.setdefault(info.password, []).append(info)
    if not remaining:
        return

    total_to_find = sum(len(group) for group in remaining.values())
    if not dictionary_path.is_file():
        log(f"Dictionary must be an existing file: '{dictionary_path}'. "
            "Skipping dictionary attack and going straight to brute force.")
        return

    log(f"Running dictionary attack against '{dictionary_path}'...")
    start = time.perf_counter()
    lines_scanned = 0
    candidates_checked = 0
    cracked_count = 0
    stopped_early = False

    try:
        # latin-1 preserves raw byte values when processing wordlists that
        # contain bytes outside UTF-8. Accepted test passwords are ASCII.
        with dictionary_path.open("r", encoding="latin-1") as wordlist:
            for raw_line in wordlist:
                if should_stop():
                    log("Dictionary attack cancelled.")
                    stopped_early = True
                    break

                lines_scanned += 1
                candidate = raw_line.strip()
                if lines_scanned == 1 and candidate.startswith("\xef\xbb\xbf"):
                    candidate = candidate[3:]
                if not candidate:
                    continue  # blank lines are not password attempts

                candidates_checked += 1
                if candidate in remaining:
                    matches = remaining.pop(candidate)
                    elapsed = time.perf_counter() - start
                    for info in matches:
                        info.cracked = True
                        info.attempts += candidates_checked
                        info.time_taken += elapsed
                        _report_crack(info, info.attempts, "dictionary search", log)
                    cracked_count += len(matches)
                    if not remaining:
                        break
    except OSError as exc:
        # Includes read errors as well as permission problems / a bad path.
        log(f"Unable to read dictionary '{dictionary_path}': {exc}. "
            "Continuing with brute force for unresolved passwords.")
    finally:
        # Every unresolved target was checked against every usable candidate
        # scanned so far. Preserve time spent here when brute force follows.
        elapsed = time.perf_counter() - start
        for group in remaining.values():
            for info in group:
                info.attempts += candidates_checked
                info.time_taken += elapsed

    if not stopped_early:
        elapsed = time.perf_counter() - start
        log(f"Dictionary attack complete: scanned {lines_scanned:,} lines "
            f"({candidates_checked:,} candidates) in {elapsed:.2f}s, "
            f"cracked {cracked_count} of {total_to_find} password(s).")

        if lines_scanned < 100:
            log(f"Note: this wordlist contains {lines_scanned} scanned line(s). "
                "If you expected a large wordlist such as rockyou.txt, "
                "check that the selected file is complete.")


def _report_crack(pw_info: PasswordInfo, attempts_at_crack: int, source: str, log: LogFn) -> None:
    timing = "instantly!" if pw_info.time_taken < 0.01 else f"in {pw_info.time_taken:.2f} seconds"
    log(f"Your password '{pw_info.password}' was cracked {timing}")
    log(f"Total attempts to find this password: {attempts_at_crack:,} (found by {source})")


# ---- Brute force attack -------------------------------------------------

def brute_force_attack(
    passwords: list[PasswordInfo],
    log: LogFn = _default_log,
    confirm: ConfirmFn = _default_confirm,
    should_stop: StopFn = _default_stop,
) -> None:
    completed: dict[str, PasswordInfo] = {}
    for pw_info in passwords:
        if pw_info.cracked:
            continue

        if should_stop():
            log("Brute force cancelled.")
            return

        # Reuse a completed result for repeated targets instead of repeating
        # the same potentially expensive brute-force loop or confirmation.
        prior = completed.get(pw_info.password)
        if prior is not None:
            pw_info.attempts = prior.attempts
            pw_info.time_taken = prior.time_taken
            pw_info.cracked = prior.cracked
            pw_info.too_long = prior.too_long
            pw_info.skipped = prior.skipped
            if pw_info.cracked:
                _report_crack(pw_info, pw_info.attempts, "brute force machine", log)
            continue

        if len(pw_info.password) > MAX_BRUTE_FORCE_LENGTH:
            pw_info.too_long = True
            completed[pw_info.password] = pw_info
            log(f"Sorry, '{pw_info.password}' is longer than "
                f"{MAX_BRUTE_FORCE_LENGTH} characters - too long for the "
                "brute force machine to search in a reasonable amount of time.")
            continue

        keyspace = estimate_keyspace(len(pw_info.password))
        if keyspace >= LARGE_KEYSPACE_WARNING and not confirm(pw_info.password, keyspace):
            pw_info.skipped = True
            completed[pw_info.password] = pw_info
            log(f"Skipping brute force for '{pw_info.password}'.")
            continue

        start = time.perf_counter()
        base_attempts = pw_info.attempts  # carry over dictionary-attack attempts
        found = False

        for length in range(1, len(pw_info.password) + 1):
            for guess_tuple in itertools.product(ALPHABET, repeat=length):
                if should_stop():
                    log("Brute force cancelled.")
                    return

                pw_info.attempts += 1

                if (pw_info.attempts - base_attempts) % PROGRESS_REPORT_INTERVAL == 0:
                    guess_so_far = "".join(guess_tuple)
                    log(f"Attempts so far: {pw_info.attempts:,}, current guess: {guess_so_far}")

                if "".join(guess_tuple) == pw_info.password:
                    pw_info.cracked = True
                    pw_info.time_taken += time.perf_counter() - start
                    found = True
                    _report_crack(pw_info, pw_info.attempts, "brute force machine", log)
                    break

            if found:
                break

        if not found and not pw_info.skipped:
            log(f"'{pw_info.password}' could not be cracked by brute force.")
        completed[pw_info.password] = pw_info


# ---- Summary -------------------------------------------------------------

def summarize(passwords: list[PasswordInfo], log: LogFn = _default_log) -> None:
    cracked = sum(1 for p in passwords if p.cracked)

    if cracked == len(passwords):
        log("All passwords were cracked. Thank you for using the program!")
    else:
        for p in passwords:
            if not p.cracked:
                if p.too_long:
                    reason = "too long for brute force"
                elif p.skipped:
                    reason = "brute force skipped by user"
                else:
                    reason = "not found within the search limit"
                log(f"'{p.password}' was NOT cracked ({reason}).")

    total_attempts = sum(p.attempts for p in passwords)
    total_time = sum(p.time_taken for p in passwords)
    time_str = "less than a second" if total_time < 0.01 else f"{total_time:.2f} seconds"
    log(f"Combined per-password time: {time_str}")
    log(f"Total attempts across all passwords: {total_attempts:,}")


# ---- Convenience wrapper ---------------------------------------------------

def run_attack(
    passwords: list[PasswordInfo],
    dictionary_path: Path,
    log: LogFn = _default_log,
    confirm: ConfirmFn = _default_confirm,
    should_stop: StopFn = _default_stop,
) -> None:
    """Dictionary attack, then brute force any leftovers, then summarize."""
    dictionary_attack(passwords, dictionary_path, log=log, should_stop=should_stop)

    if should_stop():
        return

    if any(not p.cracked for p in passwords):
        log("Dictionary attack finished. Starting brute force for any "
            "remaining passwords... this may take a while.")
        brute_force_attack(passwords, log=log, confirm=confirm, should_stop=should_stop)

    summarize(passwords, log=log)