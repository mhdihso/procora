from procora.backend import unique_columns


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
