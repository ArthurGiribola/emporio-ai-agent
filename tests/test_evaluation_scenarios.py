"""Public synthetic conversation evaluation dataset structure."""

import json
import unittest
from pathlib import Path


class EvaluationScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'conversation_scenarios.json'
        cls.dataset = json.loads(path.read_text(encoding='utf-8'))

    def test_named_suites_preserve_documented_turn_counts(self):
        expected = {'smoke': 11, 'primary': 51, 'variety': 48}
        for suite, turn_count in expected.items():
            with self.subTest(suite=suite):
                scenarios = [s for s in self.dataset['scenarios'] if s['suite'] == suite]
                self.assertGreater(len(scenarios), 0)
                self.assertEqual(sum(len(s['turns']) for s in scenarios), turn_count)

    def test_dataset_is_synthetic_and_every_turn_has_an_assertion(self):
        self.assertEqual(self.dataset['data_mode'], 'DEMO synthetic fixtures')
        ids = [scenario['id'] for scenario in self.dataset['scenarios']]
        self.assertEqual(len(ids), len(set(ids)))
        assertions = {'expected_status', 'expected_scope', 'must_call_tool', 'must_call_any',
                      'must_not_call_tools', 'must_include_all', 'must_include_any',
                      'must_not_include', 'must_not_claim_purchase', 'must_redact_answer',
                      'max_answer_words', 'expected_policy_assessment'}
        for scenario in self.dataset['scenarios']:
            for turn in scenario['turns']:
                with self.subTest(scenario=scenario['id'], user=turn['user']):
                    self.assertTrue(turn['user'].strip())
                    self.assertTrue(assertions.intersection(turn), 'turn must have a pass/fail criterion')


if __name__ == '__main__':
    unittest.main()
