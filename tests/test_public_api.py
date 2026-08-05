import procora


def test_package_version_is_part_of_the_public_api():
    assert "__version__" in procora.__all__
    assert procora.__version__
