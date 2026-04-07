"""Tests for linkedin_search pure functions (no browser required)."""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.linkedin_search import (
    build_search_url,
    is_captcha_page,
    parse_search_results,
    brave_search_profiles,
    brave_search_domain,
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

    def test_not_a_robot_detected_v1(self):
        text = "Please verify you're not a robot to continue."
        assert is_captcha_page(text) is True

    def test_automated_queries_detected(self):
        text = "We do not allow automated queries to our systems."
        assert is_captcha_page(text) is True

    def test_not_a_robot_detected_v2(self):
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


class TestBraveSearchProfiles:
    MOCK_BRAVE_RESPONSE = {
        "web": {
            "results": [
                {
                    "title": "Amy Salazar - Recruiter at Stripe",
                    "url": "https://www.linkedin.com/in/amysalazar",
                    "description": "Miami, Florida, United States · Recruiter at Stripe. Focused on engineering hiring.",
                },
                {
                    "title": "Lindsay Brown - Talent Acquisition @ Stripe",
                    "url": "https://www.linkedin.com/in/lindsaybrown15",
                    "description": "Chicago, Illinois, United States · Talent Acquisition at Stripe.",
                },
                {
                    "title": "Stripe Blog - Company News",
                    "url": "https://stripe.com/blog",
                    "description": "Latest news from Stripe.",
                },
            ]
        }
    }

    @patch("src.agents.linkedin_search.httpx")
    def test_returns_linkedin_profiles_only(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.MOCK_BRAVE_RESPONSE
        mock_httpx.get.return_value = mock_response

        results = brave_search_profiles(
            "site:linkedin.com/in recruiter Stripe", "fake-key"
        )
        assert len(results) == 2
        assert all("linkedin.com/in/" in r["linkedin_url"] for r in results)

    @patch("src.agents.linkedin_search.httpx")
    def test_parses_name_and_title(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.MOCK_BRAVE_RESPONSE
        mock_httpx.get.return_value = mock_response

        results = brave_search_profiles(
            "site:linkedin.com/in recruiter Stripe", "fake-key"
        )
        amy = next(r for r in results if "amysalazar" in r["linkedin_url"])
        assert amy["name"] == "Amy Salazar"
        assert "Recruiter" in amy["title"]

    @patch("src.agents.linkedin_search.httpx")
    def test_deduplicates_urls(self, mock_httpx):
        duped = {
            "web": {
                "results": [
                    {
                        "title": "Amy Salazar - Recruiter",
                        "url": "https://www.linkedin.com/in/amysalazar",
                        "description": "Miami, Florida, United States · Recruiter.",
                    },
                    {
                        "title": "Amy Salazar - Recruiter at Stripe",
                        "url": "https://www.linkedin.com/in/amysalazar",
                        "description": "Stripe recruiter.",
                    },
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = duped
        mock_httpx.get.return_value = mock_response

        results = brave_search_profiles("query", "fake-key")
        assert len(results) == 1

    @patch("src.agents.linkedin_search.httpx")
    def test_returns_empty_on_api_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("timeout")
        results = brave_search_profiles("query", "fake-key")
        assert results == []

    @patch("src.agents.linkedin_search.httpx")
    def test_returns_empty_on_non_200(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_httpx.get.return_value = mock_response

        results = brave_search_profiles("query", "fake-key")
        assert results == []


class TestBraveSearchDomain:
    @patch("src.agents.linkedin_search.httpx")
    def test_extracts_root_domain(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Deloitte US", "url": "https://www2.deloitte.com/us/en.html", "description": "Deloitte official site."},
                ]
            }
        }
        mock_httpx.get.return_value = mock_response

        domain = brave_search_domain("Deloitte", "fake-key")
        assert domain == "deloitte.com"

    @patch("src.agents.linkedin_search.httpx")
    def test_skips_excluded_domains(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Deloitte - LinkedIn", "url": "https://www.linkedin.com/company/deloitte", "description": ""},
                    {"title": "Deloitte US", "url": "https://www2.deloitte.com/us", "description": ""},
                ]
            }
        }
        mock_httpx.get.return_value = mock_response

        domain = brave_search_domain("Deloitte", "fake-key")
        assert domain == "deloitte.com"

    @patch("src.agents.linkedin_search.httpx")
    def test_returns_none_on_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("timeout")
        assert brave_search_domain("Deloitte", "fake-key") is None
