from pathlib import Path

import pytest

from regwatch.watch.rbi import parse_rss


@pytest.fixture
def rbi_sample_xml() -> str:
    path = Path(__file__).parent / "fixtures" / "rbi_sample.xml"
    return path.read_text()


def test_parse_rss_extracts_all_items(rbi_sample_xml: str) -> None:
    references = parse_rss(rbi_sample_xml)

    assert len(references) == 2


def test_parse_rss_extracts_correct_fields(rbi_sample_xml: str) -> None:
    references = parse_rss(rbi_sample_xml)

    first = references[0]
    assert first.notification_id == 160123
    assert first.title == "Master Direction Amendment on KYC"
