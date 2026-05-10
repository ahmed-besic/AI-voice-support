from types import SimpleNamespace

from app.adapters.faq import rank_entries


def make_entry(entry_id: str, title: str, content: str):
    return SimpleNamespace(
        id=entry_id,
        title=title,
        content=content,
        source='seed',
        metadata_json={},
    )


def test_rank_entries_prefers_relevant_matches():
    entries = [
        make_entry('1', 'Refund policy', 'Refunds are processed in five business days.'),
        make_entry('2', 'Password reset', 'Use the account recovery link to reset your password.'),
        make_entry('3', 'Billing address', 'You can update billing details in settings.'),
    ]

    results = rank_entries('refund policy', entries)

    assert len(results) == 1
    assert results[0]['id'] == '1'
    assert results[0]['title'] == 'Refund policy'


def test_rank_entries_filters_irrelevant_matches():
    entries = [
        make_entry('1', 'Refund policy', 'Refunds are processed in five business days.'),
    ]

    results = rank_entries('warehouse inventory', entries)

    assert results == []
