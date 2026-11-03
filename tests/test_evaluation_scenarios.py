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
                      'max_answer_words', 'expected_policy_assessment', 'expected_tool_sequence',
                      'must_return_product_ids', 'expected_list_prices_brl', 'expected_final_prices_brl',
                      'must_have_prior_tool'}
        for scenario in self.dataset['scenarios']:
            for turn in scenario['turns']:
                with self.subTest(scenario=scenario['id'], user=turn['user']):
                    self.assertTrue(turn['user'].strip())
                    self.assertTrue(assertions.intersection(turn), 'turn must have a pass/fail criterion')

    def test_continuity_holdout_versions_preserve_original_and_correct_table_price_assertion(self):
        root = Path(__file__).resolve().parents[1] / 'scripts' / 'holdouts'
        v1 = json.loads((root / 'continuity-18-v1.json').read_text(encoding='utf-8'))
        v2 = json.loads((root / 'continuity-18-v2.json').read_text(encoding='utf-8'))
        self.assertEqual(v1['version'], 1)
        self.assertEqual(v2['version'], 2)
        for dataset in (v1, v2):
            self.assertEqual(dataset['data_mode'], 'DEMO synthetic fixtures')
            self.assertEqual(sum(len(s['turns']) for s in dataset['scenarios']), 18)
        users_v1 = [[turn['user'] for turn in s['turns']] for s in v1['scenarios']]
        users_v2 = [[turn['user'] for turn in s['turns']] for s in v2['scenarios']]
        self.assertEqual(users_v1, users_v2)
        compare_v1 = next(turn for scenario in v1['scenarios'] if scenario['id'] == 'explicit_switch_comparison'
                          for turn in scenario['turns'] if 'Comparando esse' in turn['user'])
        compare_v2 = next(turn for scenario in v2['scenarios'] if scenario['id'] == 'explicit_switch_comparison'
                          for turn in scenario['turns'] if 'Comparando esse' in turn['user'])
        self.assertEqual(compare_v1['expected_final_prices_brl'], ['90.09', '250.00'])
        self.assertEqual(compare_v2['expected_list_prices_brl'], ['100.10', '250.00'])
        self.assertIn('preço de tabela', v2['description'])

    def test_fresh_continuity_holdout_is_multiturn_and_asserts_each_turn(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'holdouts' / 'continuity-fresh-9.json'
        dataset = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(dataset['data_mode'], 'DEMO synthetic fixtures')
        self.assertEqual(sum(len(scenario['turns']) for scenario in dataset['scenarios']), 9)
        for scenario in dataset['scenarios']:
            self.assertGreater(len(scenario['turns']), 1)
            for turn in scenario['turns']:
                self.assertTrue(turn.get('must_not_call_tools') or turn.get('must_call_tool')
                                or turn.get('expected_tool_sequence') or turn.get('must_have_prior_tool'))


if __name__ == '__main__':
    unittest.main()
