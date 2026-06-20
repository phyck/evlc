from __future__ import annotations

import socket
import threading
import unittest

import evlc


class ArgumentTests(unittest.TestCase):
    def test_direct_urls_remain_separate_items(self) -> None:
        args = [
            "https://example.test/one.m3u8?x=1&y=2",
            "https://example.test/two.m3u8?x=3&y=4",
        ]
        self.assertEqual(evlc.prepare_vlc_args(args), args)

    def test_extension_metadata_becomes_item_options(self) -> None:
        args = [
            "--http-referrer",
            "https://example.test/watch?id=1",
            "--http-user-agent",
            "Example Browser/1.0",
            r"C:\Temp\media-1.m3u8",
            ":meta-title=Example",
        ]
        self.assertEqual(
            evlc.prepare_vlc_args(args),
            [
                r"C:\Temp\media-1.m3u8",
                ":http-referrer=https://example.test/watch?id=1",
                ":http-user-agent=Example Browser/1.0",
                ":meta-title=Example",
            ],
        )

    def test_local_paths_with_spaces_remain_intact(self) -> None:
        path = r"C:\Media Files\playlist one.m3u8"
        self.assertEqual(evlc.prepare_vlc_args([path]), [path])


class RcTransportTests(unittest.TestCase):
    def test_multiple_commands_are_sent_before_clean_logout(self) -> None:
        received: list[str] = []
        ready = threading.Event()
        listener = socket.socket()
        listener.bind((evlc.RC_HOST, 0))
        old_port = evlc.RC_PORT
        evlc.RC_PORT = listener.getsockname()[1]
        listener.listen(1)

        def server() -> None:
            ready.set()
            connection, _ = listener.accept()
            with connection, listener:
                buffer = b""
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        return
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        received.append(line.decode("utf-8"))
                        connection.sendall(b"command: returned 0\n")
                        if line == b"logout":
                            return

        thread = threading.Thread(target=server)
        thread.start()
        ready.wait()
        try:
            self.assertTrue(
                evlc.enqueue_via_rc(
                    [
                        "https://example.test/one",
                        "https://example.test/two",
                    ]
                )
            )
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(
                received,
                [
                    "enqueue https://example.test/one",
                    "enqueue https://example.test/two",
                    "logout",
                ],
            )
        finally:
            evlc.RC_PORT = old_port
            listener.close()


if __name__ == "__main__":
    unittest.main()
