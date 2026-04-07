"""Tests for linkedin_search pure functions (no browser required)."""

import pytest

from src.agents.linkedin_search import (
    build_search_url,
    is_captcha_page,
    parse_search_results,
)


class TestBuildSearchUrl:
    def test_basic_query(self):
        url = build_search_url("recruiter stripe site:linkedin.com/in")
        assert url.startswith("https://www.google.com/search?q=")
        assert "num=10" in url

    def test_spaces_encoded(self):
        url = build_search_url("Amy Salazar Stripe recruiter")
        assert " " not in url
        assert "Amy" in url

    def test_special_chars_encoded(self):
        url = build_search_url("site:linkedin.com/in recruiter & hiring")
        assert "&" not in url.split("?q=")[1].split("&num=")[0]

    def test_num_param_present(self):
        url = build_search_url("test query")
        assert url.endswith("&num=10")


class TestIsCaptchaPage:
    def test_unusual_traffic_detected(self):
        text = "Our systems have detected unusual traffic from your computer network."
        assert is_captcha_page(text) is True

    def test_captcha_keyword_detected(self):
        text = "Please complete the captcha to continue using Google."
        assert is_captcha_page(text) is True

    def test_blocked_keyword_detected(self):
        text = "Your request has been blocked by our automated systems."
        assert is_captcha_page(text) is True

    def test_automated_queries_detected(self):
        text = "We do not allow automated queries to our systems."
        assert is_captcha_page(text) is True

    def test_not_a_robot_detected(self):
        text = "Please verify you are not a robot before proceeding."
        assert is_captcha_page(text) is True

    def test_case_insensitive(self):
        assert is_captcha_page("UNUSUAL TRAFFIC detected") is True
        assert is_captcha_page("CAPTCHA required") is True

    def test_normal_search_page_not_detected(self):
        text = (
            "Amy Salazar - Stripe\n"
            "LinkedIn · Amy Salazar 2.6K+ followers\n"
            "https://www.linkedin.com/in/amysalazar\n"
            "Miami, Florida, United States · Stripe\n"
        )
        assert is_captcha_page(text) is False

    def test_empty_string_not_detected(self):
        assert is_captcha_page("") is False


class TestParseSearchResults:
    SAMPLE_TEXT = (
        "Amy Salazar - Stripe\n"
        "LinkedIn · Amy Salazar 2.6K+ followers\n"
        "https://www.linkedin.com/in/amysalazar\n"
        "Miami, Florida, United States · Stripe\n"
        "High-touch, human-centric recruiter. Focused on 0-to-1 builds...\n"
        "\n"
        "Lindsay Brown - Talent Acquisition @ Stripe\n"
        "LinkedIn · Lindsay Brown 6.5K+ followers\n"
        "https://www.linkedin.com/in/lindsaybrown15\n"
        "Chicago, Illinois, United States · Recruiter · Stripe\n"
    )

    def test_returns_list(self):
        results = parse_search_results(self.SAMPLE_TEXT)
        assert isinstance(results, list)

    def test_finds_expected_profiles(self):
        results = parse_search_results(self.SAMPLE_TEXT)
        urls = [r["linkedin_url"] for r in results]
        assert any("amysalazar" in u for u in urls)
        assert any("lindsaybrown15" in u for u in urls)

    def test_result_has_required_keys(self):
        results = parse_search_results(self.SAMPLE_TEXT)
        assert len(results) > 0
        for r in results:
            assert "name" in r
            assert "title" in r
            assert "location" in r
            assert "linkedin_url" in r

    def test_deduplicates_same_url(self):
        # Same URL appearing twice in text should yield only one result
        doubled = self.SAMPLE_TEXT + self.SAMPLE_TEXT
        results = parse_search_results(doubled)
        urls = [r["linkedin_url"] for r in results]
        assert len(urls) == len(set(urls))

    def test_empty_text_returns_empty_list(self):
        assert parse_search_results("") == []

    def test_no_linkedin_urls_returns_empty_list(self):
        text = "Google search results page with no LinkedIn profiles found."
        assert parse_search_results(text) == []

    def test_linkedin_url_format(self):
        results = parse_search_results(self.SAMPLE_TEXT)
        for r in results:
            assert r["linkedin_url"].startswith("https://www.linkedin.com/in/")

    def test_name_extracted(self):
        results = parse_search_results(self.SAMPLE_TEXT)
        names = [r["name"] for r in results]
        assert any("Amy Salazar" in n for n in names)

    def test_location_extracted(self):
        results = parse_search_results(self.SAMPLE_TEXT)
        locations = [r["location"] for r in results]
        assert any(loc and ("Miami" in loc or "Florida" in loc or "Chicago" in loc or "Illinois" in loc) for loc in locations)

    def test_single_profile(self):
        text = (
            "Jane Doe - Engineering Manager at Acme\n"
            "LinkedIn · Jane Doe 1.2K+ followers\n"
            "https://www.linkedin.com/in/janedoe-eng\n"
            "San Francisco, California, United States · Acme\n"
        )
        results = parse_search_results(text)
        assert len(results) == 1
        assert "janedoe-eng" in results[0]["linkedin_url"]
