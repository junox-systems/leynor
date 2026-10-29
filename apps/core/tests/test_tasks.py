from unittest import mock

from django.core import mail
from django.test import TestCase
from django_q.tasks import async_task, result

from apps.core.tasks import retry


class RetryTests(TestCase):
    @mock.patch("apps.core.tasks.time.sleep")
    def test_retries_listed_errors_then_succeeds(self, sleep):
        calls = []

        @retry(OSError, retries=5)
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise OSError("smtp down")
            return "sent"

        self.assertEqual(flaky(), "sent")
        self.assertEqual(len(calls), 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    @mock.patch("apps.core.tasks.time.sleep")
    def test_gives_up_after_retries_with_capped_backoff(self, sleep):
        @retry(OSError, retries=5, max_backoff=4)
        def broken():
            raise OSError("smtp down")

        with self.assertRaises(OSError):
            broken()
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2, 4, 4, 4])

    def test_does_not_retry_other_errors(self):
        calls = []

        @retry(OSError)
        def bug():
            calls.append(1)
            raise ValueError("bug")

        with self.assertRaises(ValueError):
            bug()
        self.assertEqual(len(calls), 1)


class AsyncTaskTests(TestCase):
    """Q_CLUSTER["sync"] in test settings runs tasks inline, through the ORM broker path."""

    def test_enqueued_task_runs_and_stores_result(self):
        task_id = async_task(
            "apps.core.tasks.send_test_email", "Hi", "Body", ["a@example.com"]
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["a@example.com"])
        self.assertIsNone(result(task_id))
