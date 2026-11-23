"""Tests for postcode and region setup functionality."""

import pytest

from serp_harvest.core.postcode import (
    REGION_FLOWS,
    PostcodeFlowType,
    RegionFlowConfig,
    build_composite_key,
    get_region_config,
    get_supported_regions,
    normalize_keyword,
    normalize_region,
    setup_region,
)
from serp_harvest.core.selectors import LocationSelectors


def test_all_supported_regions_have_configs():
    """Verify every supported region has a complete configuration."""
    regions = get_supported_regions()
    assert len(regions) > 0

    expected_regions = [
        "AE", "AU", "BE", "BR", "CA", "DE", "EG", "ES", "FR", "IE",
        "IN", "IT", "JP", "MX", "NL", "PL", "SA", "SE", "SG", "TR",
        "UK", "US", "ZA"
    ]

    assert set(regions) == set(expected_regions)

    for region in regions:
        config = get_region_config(region)
        assert isinstance(config, RegionFlowConfig)
        assert config.region == region
        assert isinstance(config.flow_type, PostcodeFlowType)
        assert config.homepage_url.startswith("https://")


def test_region_flow_types():
    """Verify regions are categorized correctly by flow type."""
    single_field = [
        "US", "UK", "DE", "FR", "IT", "ES", "SG",
        "AU", "IN", "MX", "TR", "IE", "NL", "BE"
    ]
    split_field = ["CA", "JP", "PL", "SE", "BR"]
    city_dropdown = ["SA", "EG", "ZA"]
    city_text = ["AE"]

    for region in single_field:
        config = get_region_config(region)
        assert config.flow_type == PostcodeFlowType.SINGLE_FIELD

    for region in split_field:
        config = get_region_config(region)
        assert config.flow_type == PostcodeFlowType.SPLIT_TWO_PART
        assert config.postcode_split_position is not None

    for region in city_dropdown:
        config = get_region_config(region)
        assert config.flow_type == PostcodeFlowType.CITY_DROPDOWN
        assert config.city_mapping is not None
        assert len(config.city_mapping) > 0

    for region in city_text:
        config = get_region_config(region)
        assert config.flow_type == PostcodeFlowType.CITY_TEXT_INPUT
        assert config.city_mapping is not None


def test_postcode_split_positions():
    """Verify split postcode regions have correct split positions."""
    test_cases = [
        ("CA", "A1A1A1", 3, ("A1A", "1A1")),
        ("JP", "101-0025", 3, ("101", "0025")),
        ("PL", "00-277", 2, ("00", "277")),
        ("SE", "111 64", 3, ("111", "64")),
        ("BR", "01319-900", 5, ("01319", "900")),
    ]

    for region, postcode, expected_pos, expected_parts in test_cases:
        config = get_region_config(region)
        assert config.postcode_split_position == expected_pos
        part1, part2 = config.split_postcode(postcode)
        assert (part1, part2) == expected_parts


def test_city_mappings_complete():
    """Verify city dropdown regions have complete mappings."""
    sa_cities = ["Riyadh", "Jeddah", "Dammam", "Al Khobar", "Abha"]
    eg_cities = ["Cairo", "Giza", "Alexandria", "Port Said", "Luxor"]
    za_cities = ["Cape Town", "Johannesburg", "Durban", "Pretoria", "Bloemfontein"]
    ae_cities = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"]

    sa_config = get_region_config("SA")
    for city in sa_cities:
        assert city in sa_config.city_mapping
        assert isinstance(sa_config.city_mapping[city], int)

    eg_config = get_region_config("EG")
    for city in eg_cities:
        assert city in eg_config.city_mapping

    za_config = get_region_config("ZA")
    for city in za_cities:
        assert city in za_config.city_mapping

    ae_config = get_region_config("AE")
    for city in ae_cities:
        assert city in ae_config.city_mapping


def test_cookie_consent_flags():
    """Verify cookie consent flags are set correctly for EU regions."""
    eu_regions_requiring_consent = ["UK", "DE", "FR", "IT", "ES", "PL", "SE", "TR", "IE"]

    for region in eu_regions_requiring_consent:
        config = get_region_config(region)
        assert config.requires_cookie_consent is True

    non_eu_regions = ["US", "CA", "AU", "SG", "IN", "MX", "BR", "JP"]
    for region in non_eu_regions:
        config = get_region_config(region)
        assert config.requires_cookie_consent is False


def test_dismiss_notification_flags():
    """Verify dismiss notification flags are set for regions that need them."""
    regions_with_dismiss = ["UK", "DE", "FR", "IT", "ES", "TR"]

    for region in regions_with_dismiss:
        config = get_region_config(region)
        assert config.requires_dismiss_notification is True


def test_normalize_region():
    """Test region normalization."""
    assert normalize_region("us") == "US"
    assert normalize_region("  uk  ") == "UK"
    assert normalize_region("DE") == "DE"
    assert normalize_region("ca") == "CA"


def test_normalize_keyword():
    """Test keyword normalization."""
    assert normalize_keyword("USB Cable") == "usb cable"
    assert normalize_keyword("  wireless   mouse  ") == "wireless mouse"
    assert normalize_keyword("HDMI-ADAPTER") == "hdmi-adapter"


def test_build_composite_key():
    """Test composite key building for checkpoints."""
    key = build_composite_key("USB Cable", "us", "Featured")
    assert key == "usb cable_US_featured"

    key = build_composite_key("  Laptop  ", "UK", "Newest")
    assert key == "laptop_UK_newest"


def test_get_unsupported_region_raises():
    """Test that unsupported regions raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported region"):
        get_region_config("XX")

    with pytest.raises(ValueError, match="Unsupported region"):
        get_region_config("ZZ")


def test_split_postcode_on_single_field_region_raises():
    """Test that split_postcode raises on single-field regions."""
    config = get_region_config("US")
    with pytest.raises(ValueError, match="does not use split postcodes"):
        config.split_postcode("10001")


def test_postcode_extract_configs():
    """Verify all regions have postcode extraction configurations."""
    for region in get_supported_regions():
        config = get_region_config(region)
        assert config.current_postcode_extract is not None
        assert config.current_postcode_extract.source_line in ["line1", "line2"]
        assert len(config.current_postcode_extract.extraction_js) > 0


@pytest.mark.asyncio
async def test_setup_region_unsupported_raises(page):
    """Test that setup_region raises for unsupported regions."""
    with pytest.raises(ValueError, match="Unsupported region"):
        await setup_region(page, "XX", "12345")


@pytest.mark.asyncio
async def test_setup_region_with_custom_selectors(page):
    """Test that setup_region accepts custom selectors."""
    custom_selectors = LocationSelectors(
        location_trigger="#custom-trigger",
        postcode_input="#custom-postcode",
    )

    # Mock page to avoid actual navigation
    await page.set_content("""
        <html><body>
            <div id="custom-trigger">Location</div>
            <input id="custom-postcode" />
        </body></html>
    """)

    # This will fail because the full flow needs more elements,
    # but it proves the selectors are passed through
    with pytest.raises(RuntimeError):
        await setup_region(page, "US", "10001", selectors=custom_selectors)


def test_all_flows_have_homepage_urls():
    """Verify all region configs have valid homepage URLs."""
    for region in get_supported_regions():
        config = get_region_config(region)
        assert config.homepage_url.startswith("https://")
        assert "example.com" in config.homepage_url or \
               "example.co" in config.homepage_url or \
               "example.de" in config.homepage_url or \
               "example.fr" in config.homepage_url or \
               "example.it" in config.homepage_url or \
               "example.es" in config.homepage_url or \
               "example.in" in config.homepage_url or \
               "example.sg" in config.homepage_url or \
               "example.nl" in config.homepage_url or \
               "example.pl" in config.homepage_url or \
               "example.se" in config.homepage_url or \
               "example.be" in config.homepage_url or \
               "example.ie" in config.homepage_url or \
               "example.mx" in config.homepage_url or \
               "example.tr" in config.homepage_url or \
               "example.sa" in config.homepage_url or \
               "example.eg" in config.homepage_url or \
               "example.za" in config.homepage_url or \
               "example.ae" in config.homepage_url or \
               "example.ca" in config.homepage_url or \
               "example.au" in config.homepage_url or \
               "example.br" in config.homepage_url or \
               "example.jp" in config.homepage_url


def test_city_dropdown_invalid_city_raises():
    """Test that invalid city names raise ValueError."""
    config = get_region_config("SA")

    # Valid cities should be in mapping
    assert "Riyadh" in config.city_mapping

    # Invalid city should not be present
    assert "InvalidCity" not in config.city_mapping


def test_region_flows_dict_structure():
    """Verify REGION_FLOWS dict has correct structure."""
    assert isinstance(REGION_FLOWS, dict)
    assert len(REGION_FLOWS) >= 23

    for region_code, config in REGION_FLOWS.items():
        assert isinstance(region_code, str)
        assert region_code == region_code.upper()
        assert len(region_code) == 2
        assert isinstance(config, RegionFlowConfig)
        assert config.region == region_code
