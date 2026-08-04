import pytest

from procora.backend import managed_cursor, unique_columns


def descriptions(*names):
    return [(name,) for name in names]


def test_unique_columns_handles_repeated_names():
    assert unique_columns(descriptions("Name", "Name")) == ("Name", "Name_2")


def test_unique_columns_never_collides_with_existing_suffixes():
    assert unique_columns(descriptions("Name", "Name", "Name_2")) == (
        "Name",
        "Name_2",
        "Name_2_2",
    )
    assert unique_columns(descriptions("x", "x_2", "x")) == ("x", "x_2", "x_3")


def test_unique_columns_handles_empty_and_generated_names():
    assert unique_columns(descriptions("", "", "column_1")) == (
        "column_1",
        "column_2",
        "column_1_2",
    )
    assert unique_columns(descriptions(None, None)) == ("column_1", "column_2")


def test_cursor_close_failure_does_not_mask_active_database_error():
    class BrokenCursor:
        def close(self):
            raise RuntimeError("close failed")

    with pytest.raises(ValueError, match="database failed"), managed_cursor(BrokenCursor()):
        raise ValueError("database failed")


def test_cursor_close_failure_is_visible_after_success():
    class BrokenCursor:
        def close(self):
            raise RuntimeError("close failed")

    with pytest.raises(RuntimeError, match="close failed"), managed_cursor(BrokenCursor()):
        pass
