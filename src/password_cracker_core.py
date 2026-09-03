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
    return len(ALPHABET) ** length


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
    """Scan a wordlist once, checking every line against every
    not-yet-cracked password. Mutates each PasswordInfo in place."""
    remaining = {p.password: p for p in passwords if not p.cracked}
    if not remaining:
        return

    total_to_find = len(remaining)

    if not dictionary_path.exists():
        log(f"Dictionary file not found at '{dictionary_path}'. "
            "Skipping dictionary attack and going straight to brute force.")
        return

    log(f"Running dictionary attack against '{dictionary_path}'...")
    start = time.perf_counter()
    lines_scanned = 0
    cracked_count = 0
    stopped_early = False

    # BUG FIX: real wordlists like rockyou.txt are not reliably UTF-8 -
    # they mix encodings and contain raw bytes that aren't valid UTF-8
    # sequences. Opening with encoding="utf-8", errors="ignore" silently
    # drops or mangles those bytes, which can corrupt the exact line a
    # target password sits on and make a real match fail to compare
    # equal - which looked like "the password is in the list but never
    # gets cracked." latin-1 maps every single byte (0x00-0xFF) to a
    # real character one-to-one, so it can never fail to decode and
    # never drops or shifts a byte. Plain ASCII passwords (which is all
    # this tool accepts - see ALPHABET) are unaffected either way, but
    # every line's exact bytes are now preserved intact.
    with dictionary_path.open("r", encoding="latin-1") as f:
        for raw_line in f:
            if should_stop():
                log("Dictionary attack cancelled.")
                stopped_early = True
                break

            lines_scanned += 1
            # .strip() (not just a trailing-newline rstrip) also clears
            # stray \r line endings, tabs, and incidental whitespace that
            # show up in real-world wordlists - matching how the
            # user-entered password is already .strip()'d.
            candidate = raw_line.strip()

            # Defensive: if this file was ever re-saved by an editor that
            # adds a UTF-8 byte-order mark, that BOM lands only on line 1
            # and - decoded as latin-1 - shows up as the 3 stray
            # characters below, silently breaking a match on whatever
            # word happens to be first in the list.
            if lines_scanned == 1 and candidate.startswith("\xef\xbb\xbf"):
                candidate = candidate[3:]

            if not candidate:
                continue

            if candidate in remaining:
                pw_info = remaining.pop(candidate)
                pw_info.cracked = True
                pw_info.attempts = lines_scanned
                pw_info.time_taken = time.perf_counter() - start
                cracked_count += 1
                _report_crack(pw_info, lines_scanned, "dictionary search", log)

                if not remaining:
                    break  # every password cracked, no need to keep scanning

    # Anything still uncracked was compared against every scanned line once.
    for pw_info in remaining.values():
        pw_info.attempts = lines_scanned

    if not stopped_early:
        elapsed = time.perf_counter() - start
        log(f"Dictionary attack complete: scanned {lines_scanned:,} lines in "
            f"{elapsed:.2f}s, cracked {cracked_count} of {total_to_find} password(s).")

        # Diagnostic: a real rockyou.txt has ~14.3 million lines. If the
        # file we just scanned has suspiciously few, it's very likely a
        # placeholder, a partial/interrupted download, or the wrong file -
        # flag that immediately instead of leaving a silent "0 cracked"
        # that just looks like a matching bug.
        if lines_scanned < 100:
            log(f"Note: that wordlist only contains {lines_scanned} line(s). "
                "If you expected the full rockyou.txt (~14.3 million entries), "
                f"the file at '{dictionary_path}' is likely incomplete, a "
                "placeholder, or the wrong file - worth checking its size.")


def _report_crack(pw_info: PasswordInfo, attempts_at_crack: int, source: str, log: LogFn) -> None:
    timing = "instantly!" if pw_info.time_taken < 0.01 else f"in {pw_info.time_taken:.2f} seconds"
    log(f"Your password '{pw_info.password}' was cracked {timing}")
    log(f"It took the {source} {attempts_at_crack:,} attempts to find your password")


# ---- Brute force attack -------------------------------------------------

def brute_force_attack(
    passwords: list[PasswordInfo],
    log: LogFn = _default_log,
    confirm: ConfirmFn = _default_confirm,
    should_stop: StopFn = _default_stop,
) -> None:
    for pw_info in passwords:
        if pw_info.cracked:
            continue

        if should_stop():
            log("Brute force cancelled.")
            return

        if len(pw_info.password) > MAX_BRUTE_FORCE_LENGTH:
            pw_info.too_long = True
            log(f"Sorry, '{pw_info.password}' is longer than "
                f"{MAX_BRUTE_FORCE_LENGTH} characters - too long for the "
                "brute force machine to search in a reasonable amount of time.")
            continue

        keyspace = estimate_keyspace(len(pw_info.password))
        if keyspace >= LARGE_KEYSPACE_WARNING and not confirm(pw_info.password, keyspace):
            pw_info.skipped = True
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
                    pw_info.time_taken = time.perf_counter() - start
                    found = True
                    _report_crack(pw_info, pw_info.attempts, "brute force machine", log)
                    break

            if found:
                break

        if not found and not pw_info.skipped:
            log(f"'{pw_info.password}' could not be cracked by brute force.")


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

    if len(passwords) > 1:
        total_attempts = sum(p.attempts for p in passwords)
        total_time = sum(p.time_taken for p in passwords)
        time_str = "less than a second" if total_time < 0.01 else f"{total_time:.2f} seconds"
        log(f"Total time across all passwords: {time_str}")
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