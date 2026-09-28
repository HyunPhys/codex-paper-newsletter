from paper_newsletter.doi import normalize_title


def test_normalize_title_for_doi_lookup() -> None:
    assert normalize_title("Information in 4D-STEM: Where it is, and How to Use it") == (
        "information in 4d stem where it is and how to use it"
    )
