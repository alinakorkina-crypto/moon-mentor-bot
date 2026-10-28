"""Run release tests without credentials, sockets or real subprocesses."""
import os
import socket
import subprocess
import unittest
from unittest.mock import patch


def main() -> int:
    environment = {
        "BOT_TOKEN": "123456:offline-test-token",
        "OPENAI_API_KEY": "offline-test-only",
    }
    with patch.dict(os.environ, environment, clear=True), \
         patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket.socket, "connect_ex", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")), \
         patch.object(subprocess, "Popen", side_effect=AssertionError("Subprocess forbidden")), \
         patch.object(subprocess, "run", side_effect=AssertionError("Subprocess forbidden")):
        suite = unittest.defaultTestLoader.discover(os.path.dirname(__file__) or ".", pattern="test*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
