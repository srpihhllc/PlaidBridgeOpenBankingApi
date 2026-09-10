import app.workers as workers_init


def test_workers_init_exports():
    """Verify that worker initialization exposes expected symbols."""
    # Assert specific functions/classes exported in app/workers/__init__.py
    assert hasattr(workers_init, "sync_worker")

    # If __all__ is defined, verify its contents
    if hasattr(workers_init, "__all__"):
        assert isinstance(workers_init.__all__, list)
        assert len(workers_init.__all__) > 0


def test_init_workers_execution(app):
    """Test worker initialization logic with app context."""
    with app.app_context():
        # Call the actual initialization function defined in app/workers/__init__.py
        if hasattr(workers_init, "init_workers"):
            result = workers_init.init_workers(app)
            assert result is not False
