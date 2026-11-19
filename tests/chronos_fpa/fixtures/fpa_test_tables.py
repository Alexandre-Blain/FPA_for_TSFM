"""Small paired tables shared by checkpoint and inventory integration tests."""
import pandas as pd


def group_tables(step=0, series="001"):
    key = dict(source="synthetic", dataset_name="demo", series_id=series,
               window_id=0, window_start=0, context_len=4, horizon=3,
               branch_mode="single", branch_step=step)
    summaries, steps = [], []
    for token in (2, 3):
        summaries.append(dict(key, token_id=token, is_base_token=token == 2, n_steps=3-step))
        for h in range(3):
            steps.append(dict(key, token_id=token, forecast_step=h,
                              relative_step_after_branch=h-step, law_shift_h=float(token-2),
                              base_q10=0., base_q50=1., base_q90=2.,
                              branch_q10=0., branch_q50=float(token-1), branch_q90=3.))
    return pd.DataFrame(steps), pd.DataFrame(summaries)
