"""The recorded campaign overrun must remain a failed compliance check."""
import audit_chronos_incremental as audit


def test_small_elapsed_overrun_is_not_rounded_into_compliance(monkeypatch):
    monkeypatch.setattr(audit, 'charged_seconds', lambda run: 57624.88339270029)
    monkeypatch.setattr(audit, 'new_bytes', lambda run: 485924310)
    result = audit.resource_compliance(None, {
        'maximum_model_seconds': 57600, 'maximum_new_bytes': 20 * 2**30})
    assert result['passed'] is False
    assert 24.88 < result['model_seconds_over_limit'] < 24.89
    assert result['new_bytes_over_limit'] == 0
