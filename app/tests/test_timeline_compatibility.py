from app.models.timeline import TimelineEvent


def test_timeline_compatibility_shim():
    from app.models.timeline import __all__

    assert TimelineEvent.__name__ == "TimelineEvent"
    assert __all__ == ["TimelineEvent"]
