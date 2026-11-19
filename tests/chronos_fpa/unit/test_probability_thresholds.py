import unittest

import pandas as pd

from analyze_chronos_probability_thresholds import (
    DEFAULT_SCORE, GROUP, compare_thresholds, prepare_branches,
)


def fixture():
    rows = []
    for series, entropy, alternatives in [
        ("currency_1", .1, [(.01, .2), (.009, .8)]),
        ("currency_2", .3, [(.1, .4), (.06, .6)]),
    ]:
        for index, (probability, score) in enumerate([(.8, 0.)] + alternatives):
            rows.append({
                "dataset_name": "exchange_rate", "series_id": series,
                "window_id": 0, "window_start": 0, "branch_mode": "single",
                "branch_step": 0, "token_id": 100 + index,
                "token_probability": probability, "is_base_token": index == 0,
                "normalized_token_entropy": entropy, DEFAULT_SCORE: score,
            })
    return pd.DataFrame(rows)


class ProbabilityThresholdTests(unittest.TestCase):
    def test_inclusive_threshold_and_base_exclusion(self):
        frame = prepare_branches(fixture(), DEFAULT_SCORE)
        selections, _, _, _ = compare_thresholds(frame, [0., .01, .05], DEFAULT_SCORE)
        self.assertEqual(len(selections[0.]), 4)
        self.assertEqual(len(selections[.01]), 3)
        self.assertEqual(len(selections[.05]), 2)
        self.assertTrue(selections[.01].token_probability.eq(.01).any())
        self.assertFalse(selections[0.].is_base_token.any())

    def test_identifiers_and_matched_groups_are_preserved(self):
        frame = prepare_branches(fixture(), DEFAULT_SCORE)
        _, coverage, _, common = compare_thresholds(frame, [0., .01, .05], DEFAULT_SCORE)
        self.assertEqual(coverage.iloc[0].retained_windows, 2)
        self.assertEqual(coverage.iloc[0].retained_groups, 2)
        self.assertEqual(len(common), 1)
        self.assertEqual(next(iter(common))[GROUP.index("series_id")], "currency_2")

    def test_original_scores_and_index_do_not_change_after_filtering(self):
        frame = prepare_branches(fixture(), DEFAULT_SCORE)
        selected, _, _, _ = compare_thresholds(frame, [0., .01, .05], DEFAULT_SCORE)
        pd.testing.assert_frame_equal(selected[.05], frame.loc[frame.token_probability >= .05])
        self.assertEqual(selected[.05][DEFAULT_SCORE].tolist(), [.4, .6])
        self.assertEqual(selected[.05].model_distribution_uncertainty_index.tolist(), [.8333333333333334] * 2)

    def test_empty_cutoff_and_constant_correlations_are_explicit(self):
        frame = prepare_branches(fixture(), DEFAULT_SCORE)
        _, coverage, correlations, common = compare_thresholds(frame, [0., 1.], DEFAULT_SCORE)
        self.assertEqual(len(common), 0)
        self.assertTrue(coverage.loc[coverage.threshold == 1., "retained_branches"].eq(0).all())
        empty = correlations.loc[correlations.threshold == 1.]
        self.assertTrue(empty.spearman.isna().all())
        self.assertTrue(empty.n_pairs.eq(0).all())

    def test_bad_probabilities_and_duplicate_keys_fail(self):
        source = fixture()
        source.loc[1, "token_probability"] = 1.1
        with self.assertRaises(ValueError):
            prepare_branches(source, DEFAULT_SCORE)
        with self.assertRaises(ValueError):
            prepare_branches(pd.concat([fixture(), fixture().iloc[:1]]), DEFAULT_SCORE)


if __name__ == "__main__":
    unittest.main()
