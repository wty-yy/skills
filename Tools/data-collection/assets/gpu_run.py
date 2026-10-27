"""Request GPU memory before replacing this process with the user's command.

Quick Start:
    python3 gpu_run.py --socket /run/data-collection/control.sock -- python3 train.py

Notes:
    Run as the authorized host UID. The command sees the selected GPU as cuda:0.
    The service authenticates SO_PEERCRED; a supplied username is never trusted.
"""

import argparse
import json
import os
import socket


def main():
    """Wait for synchronous memory release, then exec the original command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", default="/run/data-collection/control.sock")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    command = options.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("supply a command after --")
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(15)
        client.connect(options.socket)
        with client.makefile("rb") as stream:
            reply = json.loads(stream.readline(4096))
        if "error" in reply:
            parser.exit(1, reply["error"] + "\n")
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=reply["gpu_uuid"])
    os.execvpe(command[0], command, environment)


if __name__ == "__main__":
    main()
