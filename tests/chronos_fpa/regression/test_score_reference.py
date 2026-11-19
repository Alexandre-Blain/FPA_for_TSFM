"""Small frozen cases; never load a research run or model to run these tests."""
import json
from pathlib import Path

import pandas as pd
import pytest

from chronos_scales import _attach_normalized_branch_scores, _attach_temporal_forking_scores
from chronos_score import compute_forking_scores


REFERENCE = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "score_reference.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: str(case["identity"]))
def test_frozen_branch_scores_and_temporal_variants(case):
    frame = pd.DataFrame([case["inputs"]])
    frame["token_bin_forking_score"], frame["progressive_token_bin_forking_score"] = compute_forking_scores(frame)
    frame = _attach_temporal_forking_scores(_attach_normalized_branch_scores(frame))
    for name, expected in case["expected"].items():
        assert frame.iloc[0][name] == pytest.approx(expected, rel=REFERENCE["rtol"], abs=REFERENCE["atol"]), name
