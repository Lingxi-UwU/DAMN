"""Rejected requests preserve their error response without unbounded reads or dispatch."""
import unittest
from unittest.mock import Mock, patch
from server import Handler


class RejectedPostTests(unittest.TestCase):
    def handler(self, headers=None, read_error=None):
        handler = Handler.__new__(Handler)
        handler.headers = headers or {}
        handler.connection = Mock()
        handler.connection.gettimeout.return_value = 3.5
        handler.rfile = Mock()
        handler.rfile.read1.side_effect = read_error or (lambda size: b'x' * size)
        handler.send = Mock(return_value='rejected')
        return handler

    def assert_rejected(self, handler):
        self.assertEqual(handler.reject_untrusted_post(), 'rejected')
        handler.send.assert_called_once_with(403, {'error': '应用会话已失效，请刷新页面。'})
        self.assertIs(handler.close_connection, True)

    def assert_deadline_restored(self, handler):
        timeouts = [call.args[0] for call in handler.connection.settimeout.call_args_list]
        self.assertEqual(timeouts[-1], 3.5)
        for timeout in timeouts[:-1]:
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, .25)

    def test_small_known_body_is_bounded_and_socket_deadline_is_restored(self):
        handler = self.handler({'Content-Length': '4096'})
        self.assert_rejected(handler)
        handler.rfile.read1.assert_called_once_with(4096)
        self.assert_deadline_restored(handler)

    def test_unknown_large_or_chunked_body_is_never_drained(self):
        for headers in ({}, {'Content-Length': '0'}, {'Content-Length': '4097'},
                        {'Content-Length': '-1'}, {'Content-Length': 'invalid'},
                        {'Content-Length': '9' * 1000}, {'Content-Length': '٢'},
                        {'Content-Length': '2', 'Transfer-Encoding': 'chunked'}):
            with self.subTest(headers=headers):
                handler = self.handler(headers)
                self.assert_rejected(handler)
                handler.rfile.read1.assert_not_called()
                handler.rfile.read.assert_not_called()
                handler.connection.settimeout.assert_not_called()

    def test_slow_or_disconnected_body_still_rejects_and_restores_deadline(self):
        for error in (TimeoutError('fixture deadline'), ConnectionResetError('fixture disconnect')):
            with self.subTest(error=type(error).__name__):
                handler = self.handler({'Content-Length': '2'}, read_error=error)
                self.assert_rejected(handler)
                handler.rfile.read1.assert_called_once_with(2)
                self.assert_deadline_restored(handler)

    def test_trickle_body_cannot_extend_the_total_drain_deadline(self):
        handler = self.handler({'Content-Length': '4'})
        handler.rfile.read1.side_effect = [b'x', b'y', b'z', b'w']
        with patch('server.time.monotonic', side_effect=[10, 10, 10.2, 10.3]):
            self.assert_rejected(handler)
        self.assertEqual([call.args for call in handler.rfile.read1.call_args_list], [(4,), (3,)])
        self.assert_deadline_restored(handler)

    def test_trust_is_checked_before_any_untrusted_business_handling(self):
        handler = self.handler({'Content-Length': '2'})
        handler.trusted = Mock(return_value=False)
        handler.reject_untrusted_post = Mock(return_value='rejected')
        handler.archive_upload = Mock(side_effect=AssertionError('must not dispatch'))
        self.assertEqual(handler.do_POST(), 'rejected')
        handler.trusted.assert_called_once_with(True)
        handler.reject_untrusted_post.assert_called_once_with()
        handler.rfile.read1.assert_not_called()
        handler.archive_upload.assert_not_called()


    def test_small_authenticated_oversize_body_keeps_its_413_and_deadline(self):
        handler = self.handler({'Content-Length': '4097'})
        message = {'error': '更新设置请求内容过大。'}
        self.assertEqual(handler.reject_post(413, message, drain_limit=8192), 'rejected')
        handler.send.assert_called_once_with(413, message)
        handler.rfile.read1.assert_called_once_with(4097)
        handler.rfile.read.assert_not_called()
        self.assert_deadline_restored(handler)
        self.assertIs(handler.close_connection, True)

    def test_authenticated_rejection_does_not_drain_unknown_or_larger_bodies(self):
        for headers in ({'Content-Length': '8193'}, {'Content-Length': '4097', 'Transfer-Encoding': 'chunked'}):
            with self.subTest(headers=headers):
                handler = self.handler(headers)
                handler.reject_post(413, {'error': 'too large'}, drain_limit=8192)
                handler.send.assert_called_once_with(413, {'error': 'too large'})
                handler.rfile.read1.assert_not_called()
                handler.connection.settimeout.assert_not_called()

    def test_update_size_limit_rejects_before_reading_or_dispatching_json(self):
        handler = self.handler({'Content-Length': '4097'})
        handler.trusted = Mock(return_value=True)
        handler.path = '/api/updates/preferences'
        handler.server = Mock()
        handler.reject_post = Mock(return_value='rejected')
        self.assertEqual(handler.do_POST(), 'rejected')
        handler.trusted.assert_called_once_with(True)
        handler.reject_post.assert_called_once_with(413, {'error': '更新设置请求内容过大。'}, drain_limit=8192)
        handler.rfile.read.assert_not_called()
        handler.server.updates.save_preferences.assert_not_called()
        handler.server.updates.check.assert_not_called()


if __name__ == '__main__':
    unittest.main()
