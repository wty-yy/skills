# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Verify key-log totals and UTC cache repair with uv run test_opencode_usage.py."""

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import opencode_usage as ou
import usage_report as report


class KeyStatsTests(unittest.TestCase):
    def test_reasoning_is_part_of_output_and_cache_writes_are_counted(self):
        stats = {
            "inputTokens": 10,
            "outputTokens": 20,
            "reasoningTokens": 8,
            "cacheReadTokens": 30,
            "cacheWriteTokens": 5,
        }
        self.assertEqual(ou.total_tokens(stats), 65)
        self.assertEqual(report.total_tokens(stats), 65)
        rows = [
            {
                "day": "2026-11-01",
                "model": "example",
                "requests": "1",
                "input_tokens": "10",
                "output_tokens": "20",
                "cache_read_tokens": "30",
                "cache_write_5m_tokens": "2",
                "cache_write_1h_tokens": "3",
                "cost_micro_cents": "100",
            }
        ]
        day = date(2026, 11, 1)
        daily, _ = ou.aggregate_usage(rows, day, day)
        self.assertEqual(ou.total_tokens(daily[day.isoformat()]), 65)
        self.assertEqual(
            report.aggregate_day_models(rows, day, day)[day.isoformat()]["example"][
                "tokens"
            ],
            65,
        )

    def test_pagination_reads_beyond_fifty_pages(self):
        pages = [
            {
                "items": [{"serviceAPIKeyID": "key", "outputTokens": 2}],
                "nextCursor": str(index + 1) if index < 50 else None,
            }
            for index in range(51)
        ]
        with patch.object(ou, "call_api", side_effect=pages) as api:
            stats = ou.fetch_day_keys("2026-11-01", [])
        self.assertEqual(api.call_count, 51)
        self.assertEqual(stats["key"]["requests"], 51)

    def test_cache_requires_utc_day_end_and_official_request_count(self):
        entry = {
            "fetchedAt": "2026-11-01T23:50:00+08:00",
            "keys": {"key": {"requests": 60}},
        }
        self.assertFalse(ou.key_day_complete("2026-11-01", entry, 60))
        entry["fetchedAt"] = "2026-11-02T08:01:00+08:00"
        self.assertFalse(ou.key_day_complete("2026-11-01", entry, 100))
        self.assertTrue(ou.key_day_complete("2026-11-01", entry, 60))
        entry["expectedRequests"] = 100
        self.assertTrue(ou.key_day_complete("2026-11-01", entry, 100))
        self.assertFalse(ou.key_day_complete("2026-11-01", entry, 101))

    def test_repairs_yesterday_but_preserves_finalized_days(self):
        with tempfile.TemporaryDirectory() as folder:
            cache_path = Path(folder) / "cache.json"
            ou.save_key_cache(
                {
                    "days": {
                        "2026-10-31": {
                            "fetchedAt": "2026-11-01T08:01:00+08:00",
                            "keys": {"key": {"requests": 40}},
                        },
                        "2026-11-01": {
                            "fetchedAt": "2026-11-01T23:50:00+08:00",
                            "keys": {"key": {"requests": 60}},
                        },
                    }
                },
                cache_path,
            )
            with (
                patch.object(ou, "datetime", wraps=datetime) as clock,
                patch.object(
                    ou, "fetch_day_keys", return_value={"key": {"requests": 100}}
                ) as fetch,
            ):
                clock.now.return_value = datetime(2026, 11, 2, 4, tzinfo=timezone.utc)
                stats, _, _ = ou.fetch_key_stats(
                    date(2026, 10, 31),
                    date(2026, 11, 1),
                    [],
                    cache_path=cache_path,
                    daily_requests={"2026-10-31": 40, "2026-11-01": 100},
                )
            fetch.assert_called_once_with("2026-11-01", [])
            self.assertEqual(stats["key"]["requests"], 140)

    def test_auth_failure_is_visible_and_retains_cached_data(self):
        with tempfile.TemporaryDirectory() as folder:
            cache_path = Path(folder) / "cache.json"
            entry = {
                "fetchedAt": "2026-11-01T23:50:00+08:00",
                "keys": {"key": {"requests": 60}},
            }
            ou.save_key_cache({"days": {"2026-11-01": entry}}, cache_path)
            with (
                patch.object(ou, "datetime", wraps=datetime) as clock,
                patch.object(
                    ou,
                    "fetch_day_keys",
                    side_effect=RuntimeError("HTTP 401 on /request-logs"),
                ),
            ):
                clock.now.return_value = datetime(2026, 11, 2, 4, tzinfo=timezone.utc)
                ou.fetch_key_stats(
                    date(2026, 11, 1), date(2026, 11, 1), [], cache_path=cache_path
                )
            cached = ou.load_key_cache(cache_path)
            self.assertEqual(cached["days"]["2026-11-01"], entry)
            self.assertEqual(cached["lastError"], "auth")

    def test_expired_logs_are_not_refetched_or_erased(self):
        with tempfile.TemporaryDirectory() as folder:
            cache_path = Path(folder) / "cache.json"
            entry = {
                "fetchedAt": "2026-10-01T23:50:00+08:00",
                "keys": {"key": {"requests": 60}},
            }
            ou.save_key_cache({"days": {"2026-10-01": entry}}, cache_path)
            with (
                patch.object(ou, "datetime", wraps=datetime) as clock,
                patch.object(ou, "fetch_day_keys") as fetch,
            ):
                clock.now.return_value = datetime(2026, 11, 2, 4, tzinfo=timezone.utc)
                ou.fetch_key_stats(
                    date(2026, 10, 1), date(2026, 10, 1), [], cache_path=cache_path
                )
            fetch.assert_not_called()
            self.assertEqual(ou.load_key_cache(cache_path)["days"]["2026-10-01"], entry)


if __name__ == "__main__":
    unittest.main()
