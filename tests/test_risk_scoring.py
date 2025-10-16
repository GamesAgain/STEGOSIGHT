from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from steganalysis.risk_scoring import RiskScorer


def test_determine_level_thresholds():
    scorer = RiskScorer()
    low = scorer.thresholds['low']
    medium = scorer.thresholds['medium']
    high = scorer.thresholds['high']

    assert scorer._determine_level(low - 0.1) == 'LOW'
    assert scorer._determine_level((low + medium) / 2) == 'MEDIUM'
    assert scorer._determine_level((medium + high) / 2) == 'HIGH'
    assert scorer._determine_level(high + 1) == 'CRITICAL'


class _DummyChiSquare:
    def __init__(self, value):
        self.value = value

    def analyze(self, file_path):
        return self.value


class _DummyHistogram:
    def __init__(self, value):
        self.value = value

    def analyze(self, file_path):
        return self.value


def test_calculate_risk_respects_weights(monkeypatch, tmp_path):
    dummy_path = tmp_path / "sample.png"
    dummy_path.write_bytes(b"PNG")

    monkeypatch.setattr(
        'steganalysis.chi_square.ChiSquareAttack',
        lambda: _DummyChiSquare(80),
        raising=False,
    )
    monkeypatch.setattr(
        'steganalysis.histogram.HistogramAnalysis',
        lambda: _DummyHistogram(20),
        raising=False,
    )

    scorer = RiskScorer()
    result = scorer.calculate_risk(dummy_path)

    chi_w = scorer.weights['chi_square']
    hist_w = scorer.weights['histogram']
    expected = (chi_w * 80 + hist_w * 20) / (chi_w + hist_w)

    assert result['score'] == pytest.approx(round(expected, 2))
    assert result['details']['chi_square'] == 80
    assert result['details']['histogram'] == 20
