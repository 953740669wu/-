"""LOCAL_FIXTURE: span ownership only; no model or corpus access."""
import unittest

from analyze_profile import KML, attribute_trace, union_us


def event(i, name, start, duration, parent=None, tid=1):
    return dict(name=name, ph='X', ts=start, dur=duration, pid=7, tid=tid,
                args=dict(event_id=i, parent_id=parent))


def phases():
    return [event(1, 'S02/zero_grad_before', 0, 10),
            event(2, 'S02/forward_loss', 10, 40),
            event(3, 'S02/zero_grad_after', 50, 1),
            event(4, 'S02/backward', 51, 39),
            event(5, 'S02/optimizer', 90, 10)]


class AttributionChecks(unittest.TestCase):
    def test_parent_thread_interval_agree(self):
        rows = phases()+[event(6, '_LinearFn', 11, 20, 2), event(7, KML, 12, 10, 6),
                         event(8, '_LinearFnBackward', 52, 30, 4), event(9, KML, 53, 20, 8)]
        result = attribute_trace(rows)
        self.assertEqual(result['issues'], [])
        self.assertEqual([x['phase'] for x in result['kml_index']], ['forward_loss', 'backward'])
        self.assertEqual([x['union_us'] for x in result['kml_groups']], [20, 10])

    def test_nested_and_duplicate_spans_not_added(self):
        rows = phases()+[event(6, KML, 12, 20, 2), event(7, KML, 14, 5, 6), event(8, KML, 12, 20, 2)]
        result = attribute_trace(rows)
        group = result['kml_groups'][0]
        self.assertEqual(group['calls'], 3)
        self.assertEqual(group['raw_duration_sum_us'], 45)
        self.assertEqual(group['union_us'], 20)
        self.assertEqual(union_us([(1, 4), (3, 8), (2, 3)]), 7)

    def test_cross_thread_parent_is_unknown(self):
        result = attribute_trace(phases()+[event(6, KML, 12, 5, 2, tid=2)])
        self.assertEqual(result['kml_index'][0]['phase'], 'UNKNOWN')
        self.assertTrue(result['issues'])

    def test_missing_parent_and_missing_event_preserved(self):
        result = attribute_trace(phases()+[event(6, KML, 12, 5, 999)])
        self.assertEqual(result['kml_index'][0]['phase'], 'UNKNOWN')
        empty = attribute_trace(phases())
        self.assertTrue(any('KML' in x for x in empty['issues']))

    def test_parent_interval_conflict_is_unknown(self):
        result = attribute_trace(phases()+[event(6, KML, 60, 5, 2)])
        self.assertEqual(result['kml_index'][0]['phase'], 'UNKNOWN')

    def test_copy_ancestor_groups_do_not_mean_all_kml(self):
        rows = phases()+[event(6, '_LinearFn', 11, 20, 2), event(7, 'aten::copy_', 12, 3, 6),
                         event(8, 'ViewBackward0', 52, 20, 4), event(9, 'aten::copy_', 53, 4, 8),
                         event(10, KML, 20, 2, 6)]
        result = attribute_trace(rows)
        groups = {x['owner']: x['calls'] for x in result['copy_groups']}
        self.assertEqual(groups, {'_LinearFn_forward_boundary': 1, 'ViewBackward_reshape_path': 1})


if __name__ == '__main__':
    unittest.main(verbosity=2)
