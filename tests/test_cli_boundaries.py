"""Synthetic CLI resource/boundary failures and explicit object/null contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from test_checks import SKILL, records, temporary_directory
from test_record_types import planned


CHECKER = SKILL / 'scripts/check_records.py'


class CliBoundaryTests(unittest.TestCase):
    def run_unchanged(self, folder, arguments, expected):
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        results = [subprocess.run([sys.executable, '-B', str(CHECKER), *arguments],
                                  capture_output=True, text=True) for _ in range(2)]
        for result in results:
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            if expected == 2:
                self.assertEqual(result.stdout, '')
                self.assertIn('error:', result.stderr)
            else:
                self.assertEqual(result.stderr, '')
                json.loads(result.stdout)
        self.assertEqual((results[0].stdout, results[0].stderr), (results[1].stdout, results[1].stderr))
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)
        return results[0]

    def test_deep_tracker_json_is_an_input_error_not_a_traceback(self):
        with temporary_directory() as folder:
            folder = Path(folder)
            source = folder / 'tracker.json'
            for text in ('[' * 200000 + ']' * 200000,
                         '{"nested":' * 200000 + 'null' + '}' * 200000):
                with self.subTest(shape=text[:12]):
                    source.write_bytes(text.encode('utf-8'))
                    self.run_unchanged(folder, [str(source)], 2)

    def test_deep_action_log_json_is_an_input_error_not_a_traceback(self):
        with temporary_directory() as folder:
            folder = Path(folder)
            source, log = folder / 'tracker.json', folder / 'actions.jsonl'
            source.write_bytes(json.dumps(planned()).encode('utf-8'))
            for text in ('[' * 200000 + ']' * 200000,
                         '{"nested":' * 200000 + 'null' + '}' * 200000):
                with self.subTest(shape=text[:12]):
                    log.write_bytes(('{}\n' + text + '\n').encode('utf-8'))
                    self.run_unchanged(folder, [str(source), '--log', str(log)], 2)

    def test_readable_nested_json_and_schema_errors_keep_distinct_exit_codes(self):
        with temporary_directory() as folder:
            folder = Path(folder)
            source, log = folder / 'tracker.json', folder / 'actions.jsonl'
            doc = planned()
            nested = None
            for _ in range(20):
                nested = {'nested': nested}
            doc['synthetic_metadata'] = nested
            source.write_bytes(json.dumps(doc).encode('utf-8'))
            log.write_bytes((json.dumps({'synthetic_metadata': nested}) + '\n').encode('utf-8'))
            result = self.run_unchanged(folder, [str(source), '--log', str(log)], 0)
            self.assertEqual(json.loads(result.stdout)['errors'], [])
            source.write_bytes(b'[]')
            result = self.run_unchanged(folder, [str(source)], 1)
            self.assertTrue(json.loads(result.stdout)['errors'])
            source.write_bytes(b'{')
            self.run_unchanged(folder, [str(source)], 2)
            source.write_bytes(b'\xff')
            self.run_unchanged(folder, [str(source)], 2)

    def test_slots_overflow_is_an_input_error_not_a_traceback(self):
        cases = [
            ('9999-12-31T23:00:00+00:00', '9999-12-31T00:00:00+00:00', 3, 168),
            ('2030-01-01T00:00:00Z', '2030-01-01T00:00:00Z', 3, 10**30),
            ('2030-01-01T00:00:00Z', '2030-01-01T00:00:00Z', 10**30, 24),
            ('2030-01-01T00:00:00Z', '0001-01-01T00:00:00+01:00', 3, 24),
        ]
        with temporary_directory() as folder:
            folder = Path(folder)
            for start, anchor, interval, window in cases:
                with self.subTest(start=start, anchor=anchor, interval=interval, window=window):
                    self.run_unchanged(folder, ['--slots', start, '--anchor', anchor,
                                              '--interval-hours', str(interval), '--window-hours', str(window)], 2)

    def test_valid_slots_at_timestamp_limits_do_not_overflow_after_last_slot(self):
        cases = [
            ('9999-12-31T22:00:00Z', '9999-12-31T22:00:00Z', 1, 1, ['9999-12-31T23:00:00+00:00']),
            ('9999-12-31T22:00:00Z', '9999-12-31T00:00:00Z', 3, 1, []),
            ('0001-01-01T00:00:00Z', '0001-01-01T00:00:00Z', 1, 2,
             ['0001-01-01T01:00:00+00:00', '0001-01-01T02:00:00+00:00']),
            ('2030-01-01T10:00:00+04:00', '2030-01-01T05:00:00Z', 3, 6,
             ['2030-01-01T12:00:00+04:00', '2030-01-01T15:00:00+04:00']),
        ]
        with temporary_directory() as folder:
            folder = Path(folder)
            for start, anchor, interval, window, expected in cases:
                with self.subTest(start=start):
                    result = self.run_unchanged(folder, ['--slots', start, '--anchor', anchor,
                                                        '--interval-hours', str(interval), '--window-hours', str(window)], 0)
                    self.assertEqual(json.loads(result.stdout), expected)
            result = self.run_unchanged(folder, ['--slots', '9999-12-31T20:00:00Z',
                '--anchor', '9999-12-31T00:00:00Z', '--interval-hours', '3', '--window-hours', '1',
                '--service-start', '9999-12-31T23:00:00Z'], 0)
            self.assertEqual(json.loads(result.stdout), [])

    def test_explicit_null_objects_are_rejected_without_mutation(self):
        documents = []
        for section in ('writer', 'service'):
            doc = planned()
            doc[section] = None
            documents.append(doc)
        doc = planned()
        doc['service']['cadence'] = None
        documents.append(doc)
        for section in ('asset', 'approval', 'scheduler', 'native_verification', 'guide',
                        'automation', 'comments', 'completion', 'production', 'performance'):
            doc = planned()
            doc['releases'][0][section] = None
            documents.append(doc)
        with temporary_directory() as folder:
            folder = Path(folder)
            source = folder / 'tracker.json'
            for index, doc in enumerate(documents):
                with self.subTest(case=index):
                    before = copy.deepcopy(doc)
                    self.assertTrue(records.validate(doc)['errors'])
                    self.assertEqual(doc, before)
                    source.write_bytes(json.dumps(doc).encode('utf-8'))
                    self.run_unchanged(folder, [str(source)], 1)

    def test_omitted_empty_and_nullable_object_fields_remain_valid_when_optional(self):
        documents = [planned()]
        empty = planned()
        empty['writer'] = {}
        empty['service']['cadence'] = {}
        empty['releases'][0]['performance'] = {}
        documents.append(empty)
        nullable = copy.deepcopy(empty)
        nullable['writer']['lease_expires_at'] = None
        nullable['service']['cadence'].update(anchor_at=None, interval_hours=None)
        nullable['releases'][0]['performance']['observed_at'] = None
        documents.append(nullable)
        with temporary_directory() as folder:
            folder = Path(folder)
            source = folder / 'tracker.json'
            for index, doc in enumerate(documents):
                with self.subTest(case=index):
                    before = copy.deepcopy(doc)
                    self.assertEqual(records.validate(doc)['errors'], [])
                    self.assertEqual(doc, before)
                    source.write_bytes(json.dumps(doc).encode('utf-8'))
                    self.run_unchanged(folder, [str(source)], 0)


if __name__ == '__main__':
    unittest.main()
