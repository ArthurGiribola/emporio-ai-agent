"""Launcher lifecycle tests. Mocked native-window calls are not real GUI runs."""

import importlib.util
import io
import os
import socket
import unittest
from urllib.parse import urlsplit
from unittest.mock import Mock, patch

from app import desktop


class DesktopTests(unittest.TestCase):
    def test_startup_traceback_is_opt_in_and_does_not_blame_dependencies(self):
        from contextlib import redirect_stderr, redirect_stdout
        for debug in ('0', '1'):
            webview = Mock()
            webview.screens = []
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(desktop.sys, 'platform', 'win32'), \
                    patch.dict('sys.modules', {'webview': webview}), \
                    patch.dict(os.environ, {'EMPORIO_DESKTOP_DEBUG': debug}), \
                    redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(desktop.main(), 2)
            self.assertIn('EMPORIO_DESKTOP_DEBUG=1', output.getvalue())
            self.assertNotIn('Install', output.getvalue())
            self.assertEqual('Traceback' in errors.getvalue(), debug == '1')
            self.assertEqual('IndexError' in errors.getvalue(), debug == '1')
            webview.create_window.assert_not_called()

    def test_non_debug_redirects_python_streams_without_replacing_os_handles(self):
        from types import SimpleNamespace
        from contextlib import redirect_stderr, redirect_stdout
        for debug in ('0', '1'):
            cli = Mock()
            output, errors = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, {'EMPORIO_DESKTOP_DEBUG': debug}), \
                    patch.dict('sys.modules', {'streamlit.web': SimpleNamespace(cli=cli)}), \
                    patch.object(desktop.os, 'dup2') as redirect, \
                    patch.object(desktop.sys, 'argv', []), \
                    redirect_stdout(output), redirect_stderr(errors):
                desktop.run_server(12345, 'desktop-test')
                redirect.assert_not_called()
                cli.main.assert_called_once_with()
                self.assertIn('--server.address=127.0.0.1', desktop.sys.argv)

    def test_server_flags_are_local_and_headless(self):
        args = desktop.server_arguments(12345, "desktop-test")
        self.assertIn("--server.address=127.0.0.1", args)
        self.assertIn("--server.headless=true", args)
        self.assertIn("--server.port=12345", args)
        self.assertIn("--browser.gatherUsageStats=false", args)

    def test_conflict_retry_stops_only_owned_workers(self):
        context = Mock()
        processes = [Mock(), Mock()]
        context.Process.side_effect = processes
        with patch.object(desktop.multiprocessing, "get_context", return_value=context), \
                patch.object(desktop, "available_port", side_effect=[1234, 5678]), \
                patch.object(desktop, "wait_until_ready", side_effect=[False, True]), \
                patch.object(desktop, "stop_server") as stop:
            with desktop.local_server() as url:
                self.assertTrue(url.startswith("http://127.0.0.1:5678/desktop-"))
                stop.assert_called_once_with(processes[0])
            self.assertEqual([c.args[0] for c in stop.call_args_list], processes)

    def test_exception_after_start_still_cleans_up(self):
        context = Mock()
        with patch.object(desktop.multiprocessing, "get_context", return_value=context), \
                patch.object(desktop, "wait_until_ready", return_value=True), \
                patch.object(desktop, "stop_server") as stop:
            with self.assertRaisesRegex(RuntimeError, "GUI failed"):
                with desktop.local_server():
                    raise RuntimeError("GUI failed")
            stop.assert_called_once_with(context.Process.return_value)

    def test_exhausted_retries_fail_without_opening_window(self):
        with patch.object(desktop.multiprocessing, "get_context"), \
                patch.object(desktop, "wait_until_ready", return_value=False), \
                patch.object(desktop, "stop_server") as stop:
            with self.assertRaises(RuntimeError):
                with desktop.local_server():
                    self.fail("Must not yield an unready server")
            self.assertEqual(stop.call_count, 3)

    def test_exited_worker_is_not_ready(self):
        process = Mock()
        process.is_alive.return_value = False
        self.assertFalse(desktop.wait_until_ready(process, "http://127.0.0.1:1234/desktop-test/"))

    def test_shutdown_uses_direct_handle_and_kill_fallback(self):
        process = Mock()
        process.is_alive.side_effect = [True, True]
        desktop.stop_server(process)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        process.close.assert_called_once()

    def test_fixed_window_adapts_to_small_screens(self):
        from types import SimpleNamespace
        self.assertEqual(desktop.window_dimensions(SimpleNamespace(width=1920,height=1080)),(560,720))
        self.assertEqual(desktop.window_dimensions(SimpleNamespace(width=480,height=640)),(448,560))

    def test_window_parameters_and_modern_renderer(self):
        from contextlib import nullcontext
        webview = Mock()
        from types import SimpleNamespace
        webview.screens = [SimpleNamespace(width=1920, height=1080)]
        with patch.object(desktop.sys, "platform", "win32"), \
                patch.dict("sys.modules", {"webview": webview}), \
                patch.object(desktop, "local_server", return_value=nullcontext("http://127.0.0.1:1234/demo/")):
            self.assertEqual(desktop.main(), 0)
        kwargs = webview.create_window.call_args.kwargs
        self.assertEqual((kwargs["width"], kwargs["height"]), (560, 720))
        self.assertFalse(kwargs["resizable"])
        self.assertFalse(kwargs["fullscreen"])
        self.assertFalse(kwargs["maximized"])
        self.assertNotIn("js_api", kwargs)
        webview.start.assert_called_once_with(gui="edgechromium", debug=False, private_mode=True)


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Optional Streamlit dependency not installed")
class DesktopServerIntegrationTests(unittest.TestCase):
    def test_real_server_cleanup_and_unrelated_port_preserved(self):
        # Real spawned server, no model or GUI. Existing listener is never reused.
        with socket.socket() as unrelated:
            unrelated.bind(("127.0.0.1", 0))
            unrelated.listen()
            occupied = unrelated.getsockname()[1]
            with desktop.local_server() as url:
                port = urlsplit(url).port
                self.assertNotEqual(port, occupied)
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    pass
            with self.assertRaises(OSError):
                socket.create_connection(("127.0.0.1", port), timeout=0.5)
            with socket.create_connection(("127.0.0.1", occupied), timeout=1):
                pass
