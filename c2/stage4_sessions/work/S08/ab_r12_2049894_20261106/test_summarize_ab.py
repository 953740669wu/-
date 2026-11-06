"""LOCAL_FIXTURE scalar statistics; no model or original suite execution."""
import unittest

from summarize_ab import median_change_percent, perf_statistics


def fixture():
    return [dict(step=i, adamw_step=i, sampled=i > 5, step_seconds=100. if i <= 5 else float(i),
        rss_peak_scope='process_lifetime', rss_before=dict(rss_bytes=100, peak_rss_bytes=200),
        rss_after=dict(rss_bytes=150, peak_rss_bytes=300)) for i in range(1, 26)]


class StatisticsChecks(unittest.TestCase):
    def test_exclude_exactly_warmup5_keep_all25(self):
        result = perf_statistics(fixture())
        self.assertEqual(result['observed20_seconds'], list(map(float, range(6, 26))))
        self.assertEqual(result['observed20_median_seconds'], 15.5)
        self.assertEqual(result['observed20_range_seconds'], [6., 25.])
        self.assertEqual(result['all25_training_seconds'], 810.)
        self.assertEqual(result['memory_samples'], 50)

    def test_missing_duplicate_or_wrong_sample_window_rejected(self):
        for rows in (fixture()[:-1], fixture()):
            if len(rows) == 25:
                rows[0]['step'] = 2
            with self.assertRaises(ValueError):
                perf_statistics(rows)
        rows = fixture(); rows[4]['sampled'] = True
        with self.assertRaises(ValueError):
            perf_statistics(rows)

    def test_nonfinite_timing_rejected(self):
        rows = fixture(); rows[10]['step_seconds'] = float('nan')
        with self.assertRaises(ValueError):
            perf_statistics(rows)

    def test_positive_is_longer_time_not_speedup(self):
        self.assertAlmostEqual(median_change_percent(4., 4.4), 10.)
        self.assertAlmostEqual(median_change_percent(4., 3.6), -10.)
        with self.assertRaises(ValueError):
            median_change_percent(0., 1.)


if __name__ == '__main__':
    unittest.main(verbosity=2)
