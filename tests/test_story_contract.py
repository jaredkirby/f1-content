"""Arithmetic and output gates over explicitly fictional evidence."""
import copy
import json
import unittest
from f1_pipeline.story_contract import validate_ledger, validate_output

EVENT_BINDING = {'path': 'config/event.json', 'sha256': 'e'*64}
EVENT_IDENTITY = {'id': 'synthetic-session', 'year': 2026, 'country_name': 'Example',
                  'session_name': 'Qualifying', 'event_date': '2026-10-10',
                  'session_key': 999999, 'meeting_key': 999999}
LEDGER_BINDING = {'path': 'story-ledger.json', 'sha256': 'a'*64}
LEDGER = {
    'schema_version': 'f1.story_ledger.v1', 'event_id': 'synthetic-session',
    'event_binding': EVENT_BINDING, 'event_identity': EVENT_IDENTITY, 'max_duration_seconds': 45,
    'sources': [{'id': 'classification', 'binding': {'path': 'evidence.json', 'sha256': 'b'*64},
                 'locator': 'Synthetic table, rows A and B'}],
    'numbers': [
        {'id': 'a-time', 'value': '60.125', 'unit': 'seconds', 'source_ids': ['classification']},
        {'id': 'b-time', 'value': '60.325', 'unit': 'seconds', 'source_ids': ['classification']},
        {'id': 'gap', 'value': '0.200', 'unit': 'seconds', 'source_ids': ['classification'],
         'derivation': {'operation': 'subtract', 'operands': ['b-time', 'a-time']}},
        {'id': 'cause-confidence', 'value': None, 'unit': 'probability', 'source_ids': []}],
    'claims': [
        {'id': 'result', 'text': 'Fictional A finished 0.200 seconds ahead of B.', 'status': 'supported',
         'source_ids': ['classification'], 'numeric_ids': ['gap']},
        {'id': 'cause', 'text': 'The cause is unknown.', 'status': 'unknown', 'source_ids': [], 'numeric_ids': []}]}
OUTPUT = {
    'schema_version': 'f1.story_output.v1', 'event_id': 'synthetic-session',
    'ledger_sha256': 'a'*64, 'stage': 'draft', 'title': 'Synthetic result', 'hook': 'A narrow fictional finish',
    'unresolved': ['claim:cause', 'number:cause-confidence'],
    'segments': [{'id': 'segment-1', 'start_seconds': 0, 'end_seconds': 12,
                  'narration': 'In this fictional fixture, A beat B by 0.200 seconds.',
                  'claim_ids': ['result'], 'source_ids': ['classification'], 'numeric_values': {'gap': '0.200'}}]}


class StoryContractTests(unittest.TestCase):
    def ledger(self, ledger):
        return validate_ledger(ledger, event_id='synthetic-session', event_binding=EVENT_BINDING, event_identity=EVENT_IDENTITY,
                               verify_binding=lambda item: None)

    def output(self, output, stage='draft'):
        return validate_output(json.dumps(output), ledger=LEDGER, ledger_binding=LEDGER_BINDING, stage=stage)

    def test_decimal_arithmetic_and_unknowns_survive_without_approval(self):
        self.assertEqual(self.ledger(LEDGER), LEDGER)
        self.assertEqual(self.output(OUTPUT)['unresolved'], OUTPUT['unresolved'])
        self.assertNotIn('human_acceptance', self.output(OUTPUT))
        wrong = copy.deepcopy(LEDGER)
        wrong['numbers'][2]['value'] = '0.199'
        with self.assertRaisesRegex(ValueError, 'arithmetic'):
            self.ledger(wrong)
        wrong['numbers'][2]['value'] = 'NaN'
        with self.assertRaises(ValueError):
            self.ledger(wrong)

    def test_unknown_numbers_and_missing_operand_sources_cannot_be_support(self):
        unknown = copy.deepcopy(LEDGER)
        unknown['claims'][0]['numeric_ids'] = ['cause-confidence']
        with self.assertRaisesRegex(ValueError, 'Unknown numbers'):
            self.ledger(unknown)
        division = copy.deepcopy(LEDGER)
        division['numbers'][0]['value'] = '0'
        division['numbers'][2]['derivation'] = {'operation': 'divide', 'operands': ['b-time', 'a-time']}
        with self.assertRaisesRegex(ValueError, 'arithmetic'):
            self.ledger(division)

    def test_timing_support_numeric_and_unresolved_mismatches_are_rejected(self):
        cases = []
        for field, value in [('end_seconds', 46), ('end_seconds', float('inf')),
                             ('start_seconds', 1), ('claim_ids', ['cause']),
                             ('source_ids', ['invented']), ('numeric_values', {'gap': '0.201'})]:
            output = copy.deepcopy(OUTPUT)
            output['segments'][0][field] = value
            cases.append(output)
        output = copy.deepcopy(OUTPUT)
        output['unresolved'] = []
        cases.append(output)
        output = copy.deepcopy(OUTPUT)
        output['human_approved'] = True
        cases.append(output)
        for output in cases:
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.output(output)

    def test_critique_is_constrained_advisory_data(self):
        critique = {k: v for k, v in OUTPUT.items() if k not in ('title', 'hook', 'segments')}
        critique.update(stage='critique', verdict='insufficient_evidence', issues=[
            {'claim_id': 'cause', 'segment_id': None, 'category': 'factual', 'comment': 'Cause remains unknown.'}])
        self.assertEqual(self.output(critique, 'critique')['verdict'], 'insufficient_evidence')
        critique['issues'][0]['claim_id'] = 'invented'
        with self.assertRaises(ValueError):
            self.output(critique, 'critique')
        critique['issues'][0]['claim_id'] = 'cause'
        critique['verdict'] = 'pass'
        with self.assertRaises(ValueError):
            self.output(critique, 'critique')

    def test_duplicate_json_fields_fail_even_if_the_last_value_is_valid(self):
        text = json.dumps(OUTPUT).replace('"stage": "draft"', '"stage": "critique", "stage": "draft"')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_output(text, ledger=LEDGER, ledger_binding=LEDGER_BINDING, stage='draft')

    def test_every_source_and_event_binding_is_verified(self):
        seen = []
        validate_ledger(LEDGER, event_id='synthetic-session', event_binding=EVENT_BINDING, event_identity=EVENT_IDENTITY,
                        verify_binding=lambda binding: seen.append(binding))
        self.assertEqual(seen, [EVENT_BINDING, LEDGER['sources'][0]['binding']])

    def test_event_identity_requires_exact_config_field_types(self):
        for field in ('year', 'session_key', 'meeting_key'):
            wrong = copy.deepcopy(LEDGER)
            wrong['event_identity'][field] = float(wrong['event_identity'][field])
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'another event'):
                self.ledger(wrong)
        wrong = copy.deepcopy(LEDGER)
        wrong['event_identity']['session_key'] = True
        with self.assertRaisesRegex(ValueError, 'another event'):
            self.ledger(wrong)
