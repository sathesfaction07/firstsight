"""Postcode and region setup for marketplace configuration.

This module configures marketplace delivery locations using a data-driven approach.
Each region has a defined flow describing how to set the delivery postcode/city.

The location setup varies significantly by region:
- Single-field postcodes (US, UK, DE, FR, IT, ES, NL, IE, IN, MX, TR)
- Split-field postcodes (CA, JP, PL, SE, BR - each splits at a different position)
- City dropdown selection (SA, EG, ZA - choose from predefined city lists)
- City text input (AE - free-form city name entry)
- Various confirm/dismiss button patterns

All DOM selectors are configurable via the LocationSelectors class to support
different site implementations.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from playwright.async_api import Page

from .selectors import DEFAULT_SELECTORS, LocationSelectors

logger = logging.getLogger(__name__)


class PostcodeFlowType(Enum):
    """Types of postcode/location entry flows."""
    SINGLE_FIELD = "single_field"
    SPLIT_TWO_PART = "split_two_part"
    CITY_DROPDOWN = "city_dropdown"
    CITY_TEXT_INPUT = "city_text_input"


@dataclass
class PostcodeExtractConfig:
    """Configuration for extracting the current postcode from the page."""
    source_line: str
    extraction_js: str


@dataclass
class RegionFlowConfig:
    """Configuration for a region's location setup flow."""
    region: str
    flow_type: PostcodeFlowType
    postcode_split_position: Optional[int] = None
    city_mapping: Optional[Dict[str, int]] = None
    requires_cookie_consent: bool = False
    requires_dismiss_notification: bool = False
    current_postcode_extract: Optional[PostcodeExtractConfig] = None
    homepage_url: str = "https://shop.example.com"

    def split_postcode(self, postcode: str) -> tuple[str, str]:
        """Split postcode into two parts for split-field regions."""
        if self.postcode_split_position is None:
            raise ValueError(f"Region {self.region} does not use split postcodes")
        cleaned = postcode.replace(" ", "").replace("-", "")
        part1 = cleaned[:self.postcode_split_position]
        part2 = cleaned[self.postcode_split_position:]
        return part1, part2


# City mappings for dropdown-based regions
SA_CITIES = {
    "Riyadh": 0, "Jeddah": 1, "Makkah Al Mukarramah": 2, "Dammam": 3,
    "Al Madinah Al Munawwarah": 4, "Al Khobar": 5, "Al Ahsa": 6, "At Taif": 7,
    "Al Jubail": 8, "Tabuk": 9, "Abha": 10, "Khamis Mushayt": 11, "Hail": 12,
    "Yanbu": 13, "Jazan": 14
}

EG_CITIES = {
    "Cairo": 0, "Giza": 1, "Alexandria": 2, "Dakahlia": 3, "Ash Sharqia": 4,
    "Gharbia": 5, "Port Said": 6, "Asyut": 7, "Sohag": 8, "Kafr El Sheikh": 9,
    "Menofia": 10, "Damietta": 11, "Suez": 12, "Beheira": 13, "Minya": 14,
    "Aswan": 15, "Qalyubia": 16, "Ismailia": 17, "Qena": 18, "Red Sea": 19,
    "Beni Suef": 20, "Matrouh": 21, "Faiyum": 22, "Luxor": 23, "North Sinai": 24,
    "New Valley": 25, "South Sinai": 26
}

ZA_CITIES = {
    "Beaufort West": 0, "Bloemfontein": 1, "Cape Town": 2, "Durban": 3,
    "East London": 4, "George": 5, "Gqeberha": 6, "Johannesburg": 7,
    "Kimberley": 8, "Klerskdorp": 9, "Mahikeng": 10, "Mbombela": 11,
    "Newcastle": 12, "Paarl": 13, "Pietermaritzburg": 14, "Polokwane": 15,
    "Pretoria": 16, "Richards Bay": 17, "Springbok": 18, "Stellenbosch": 19,
    "Upington": 20, "Welkom": 21
}

AE_CITIES = [
    "Abu Dhabi", "Ajman", "Al Ain", "Dubai", "Fujairah",
    "Ras Al Khaimah", "Sharjah", "Umm Al Quwain"
]

# Regional flow configurations
# Each region defines its unique flow for setting delivery location
REGION_FLOWS: Dict[str, RegionFlowConfig] = {
    "US": RegionFlowConfig(
        region="US",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.com",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.split(' ').slice(-1).join(' ');"  # noqa: E501
        ),
    ),
    "UK": RegionFlowConfig(
        region="UK",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        requires_dismiss_notification=True,
        homepage_url="https://shop.example.co.uk",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-8);"  # noqa: E501
        ),
    ),
    "DE": RegionFlowConfig(
        region="DE",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        requires_dismiss_notification=True,
        homepage_url="https://shop.example.de",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-6);"  # noqa: E501
        ),
    ),
    "FR": RegionFlowConfig(
        region="FR",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        requires_dismiss_notification=True,
        homepage_url="https://shop.example.fr",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-6);"  # noqa: E501
        ),
    ),
    "IT": RegionFlowConfig(
        region="IT",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        requires_dismiss_notification=True,
        homepage_url="https://shop.example.it",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-6);"  # noqa: E501
        ),
    ),
    "ES": RegionFlowConfig(
        region="ES",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        requires_dismiss_notification=True,
        homepage_url="https://shop.example.es",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-6);"  # noqa: E501
        ),
    ),
    "SG": RegionFlowConfig(
        region="SG",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.sg",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-7);"  # noqa: E501
        ),
    ),
    "AU": RegionFlowConfig(
        region="AU",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.com.au",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-5);"  # noqa: E501
        ),
    ),
    "IN": RegionFlowConfig(
        region="IN",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.in",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.slice(-7);"  # noqa: E501
        ),
    ),
    "MX": RegionFlowConfig(
        region="MX",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.com.mx",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-5);"  # noqa: E501
        ),
    ),
    "TR": RegionFlowConfig(
        region="TR",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        requires_dismiss_notification=True,
        homepage_url="https://shop.example.com.tr",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-5);"  # noqa: E501
        ),
    ),
    "IE": RegionFlowConfig(
        region="IE",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        requires_cookie_consent=True,
        homepage_url="https://shop.example.ie",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText;"
        ),
    ),
    "NL": RegionFlowConfig(
        region="NL",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.nl",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText;"
        ),
    ),
    "BE": RegionFlowConfig(
        region="BE",
        flow_type=PostcodeFlowType.SINGLE_FIELD,
        homepage_url="https://shop.example.com.be",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.split(' ').slice(-2).join(' ').split(' ')[0];"  # noqa: E501
        ),
    ),
    "CA": RegionFlowConfig(
        region="CA",
        flow_type=PostcodeFlowType.SPLIT_TWO_PART,
        postcode_split_position=3,
        homepage_url="https://shop.example.ca",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.split(' ').slice(-1).join(' ');"  # noqa: E501
        ),
    ),
    "JP": RegionFlowConfig(
        region="JP",
        flow_type=PostcodeFlowType.SPLIT_TWO_PART,
        postcode_split_position=3,
        homepage_url="https://shop.example.co.jp",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line2",
            extraction_js="return document.getElementById('delivery-location-line2').innerText.split(' ').slice(-1).join(' ').replace('-',' ');"  # noqa: E501
        ),
    ),
    "PL": RegionFlowConfig(
        region="PL",
        flow_type=PostcodeFlowType.SPLIT_TWO_PART,
        postcode_split_position=2,
        requires_cookie_consent=True,
        homepage_url="https://shop.example.pl",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-5);"  # noqa: E501
        ),
    ),
    "SE": RegionFlowConfig(
        region="SE",
        flow_type=PostcodeFlowType.SPLIT_TWO_PART,
        postcode_split_position=3,
        requires_cookie_consent=True,
        homepage_url="https://shop.example.se",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-16).split(' ').slice(0, 2).join(' ');"  # noqa: E501
        ),
    ),
    "BR": RegionFlowConfig(
        region="BR",
        flow_type=PostcodeFlowType.SPLIT_TWO_PART,
        postcode_split_position=5,
        homepage_url="https://shop.example.com.br",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-8);"  # noqa: E501
        ),
    ),
    "SA": RegionFlowConfig(
        region="SA",
        flow_type=PostcodeFlowType.CITY_DROPDOWN,
        city_mapping=SA_CITIES,
        homepage_url="https://shop.example.sa?language=en",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-6);"  # noqa: E501
        ),
    ),
    "EG": RegionFlowConfig(
        region="EG",
        flow_type=PostcodeFlowType.CITY_DROPDOWN,
        city_mapping=EG_CITIES,
        homepage_url="https://shop.example.eg?language=en",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-12).replace('...','');"  # noqa: E501
        ),
    ),
    "ZA": RegionFlowConfig(
        region="ZA",
        flow_type=PostcodeFlowType.CITY_DROPDOWN,
        city_mapping=ZA_CITIES,
        homepage_url="https://shop.example.co.za",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-4);"  # noqa: E501
        ),
    ),
    "AE": RegionFlowConfig(
        region="AE",
        flow_type=PostcodeFlowType.CITY_TEXT_INPUT,
        city_mapping={city: idx for idx, city in enumerate(AE_CITIES)},
        homepage_url="https://shop.example.ae?language=en",
        current_postcode_extract=PostcodeExtractConfig(
            source_line="line1",
            extraction_js="return document.getElementById('delivery-location-line1').innerText.slice(-5);"  # noqa: E501
        ),
    ),
}


async def setup_region(
    page: Page,
    region: str,
    postcode: str,
    selectors: LocationSelectors = DEFAULT_SELECTORS,
) -> None:
    """Set up the marketplace with the specified postcode/location.

    This function implements the full location-setup flow with all regional
    variations from the original Selenium implementation, converted to async
    Playwright. The flow is data-driven via REGION_FLOWS configuration.

    Args:
        page: Playwright Page instance
        region: Two-letter region code (uppercase)
        postcode: Postcode or city name for delivery location
        selectors: LocationSelectors instance (override for your site)

    Raises:
        ValueError: If region is not supported
        RuntimeError: If location setup fails
    """
    region_upper = region.upper()

    if region_upper not in REGION_FLOWS:
        raise ValueError(
            f"Unsupported region: {region}. "
            f"Supported regions: {', '.join(sorted(REGION_FLOWS.keys()))}"
        )

    config = REGION_FLOWS[region_upper]

    try:
        await page.goto(config.homepage_url)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_selector(selectors.location_trigger, timeout=25000)
        await page.evaluate("document.body.style.zoom = '50%'")

        # Handle cookie consent if required
        if config.requires_cookie_consent:
            await _try_accept_cookies(page, selectors)

        # Check if postcode is already set correctly
        if config.current_postcode_extract:
            try:
                # Substitute selector IDs in the extraction JS
                extraction_js = config.current_postcode_extract.extraction_js
                if "line1" in config.current_postcode_extract.source_line:
                    extraction_js = extraction_js.replace(
                        "delivery-location-line1",
                        selectors.location_display_line1.lstrip("#")
                    )
                else:
                    extraction_js = extraction_js.replace(
                        "delivery-location-line2",
                        selectors.location_display_line2.lstrip("#")
                    )

                current_postcode = await page.evaluate(extraction_js)
                current_postcode = str(current_postcode)

                # Normalize for comparison
                postcode_normalized = postcode.replace(" ", "").replace("-", "")
                current_normalized = current_postcode.replace(" ", "").replace("-", "")

                if postcode_normalized in current_normalized:
                    logger.info(f"Region {region} already has correct postcode: {current_postcode}")
                    return
            except Exception as e:
                logger.debug(f"Could not extract current postcode: {e}")

        # Proceed with location setup based on flow type
        if config.flow_type == PostcodeFlowType.SINGLE_FIELD:
            await _setup_single_field(page, postcode, selectors, config)
        elif config.flow_type == PostcodeFlowType.SPLIT_TWO_PART:
            await _setup_split_field(page, postcode, selectors, config)
        elif config.flow_type == PostcodeFlowType.CITY_DROPDOWN:
            await _setup_city_dropdown(page, postcode, selectors, config)
        elif config.flow_type == PostcodeFlowType.CITY_TEXT_INPUT:
            await _setup_city_text_input(page, postcode, selectors, config)

        logger.info(f"Region {region} configured with postcode {postcode}")

    except Exception as e:
        logger.error(f"Failed to setup region {region}: {e}")
        raise RuntimeError(f"Location setup failed for {region}: {e}") from e


async def _try_accept_cookies(page: Page, selectors: LocationSelectors) -> None:
    """Attempt to accept cookie consent banner if present."""
    try:
        cookie_btn = await page.wait_for_selector(selectors.cookie_accept, timeout=5000)
        await cookie_btn.click()
        await page.wait_for_timeout(1000)
    except Exception:
        pass


async def _setup_single_field(
    page: Page,
    postcode: str,
    selectors: LocationSelectors,
    config: RegionFlowConfig,
) -> None:
    """Handle single-field postcode entry (US, UK, DE, FR, IT, ES, etc.)."""
    await page.wait_for_load_state("domcontentloaded")

    # Click location trigger
    deliver_to = await page.wait_for_selector(selectors.location_display_line2, timeout=10000)
    await deliver_to.hover()
    await deliver_to.click()

    # Enter postcode
    postcode_input = await page.wait_for_selector(selectors.postcode_input, timeout=10000)
    await postcode_input.fill("")
    await postcode_input.fill(postcode)
    await postcode_input.press("Enter")

    # Some regions require extra wait for location update animation
    await page.wait_for_timeout(3000)

    # Dismiss notification if required
    if config.requires_dismiss_notification:
        try:
            dismiss_btn = await page.wait_for_selector(selectors.dismiss_button, timeout=5000)
            await dismiss_btn.click()
            await page.wait_for_timeout(2000)
        except Exception:
            logger.debug(f"No dismiss notification for {config.region}")


async def _setup_split_field(
    page: Page,
    postcode: str,
    selectors: LocationSelectors,
    config: RegionFlowConfig,
) -> None:
    """Handle split-field postcode entry (CA, JP, PL, SE, BR)."""
    await page.wait_for_load_state("domcontentloaded")

    part1, part2 = config.split_postcode(postcode)

    # Click location trigger
    trigger = await page.wait_for_selector(selectors.popover_trigger, timeout=10000)
    await trigger.click()

    # Fill first part
    input1 = await page.wait_for_selector(selectors.postcode_input_part1, timeout=10000)
    await input1.fill("")
    await input1.fill(part1)

    # Fill second part
    input2 = await page.wait_for_selector(selectors.postcode_input_part2, timeout=10000)
    await input2.fill("")
    await input2.fill(part2)
    await input2.press("Enter")

    await page.wait_for_timeout(3000)


async def _setup_city_dropdown(
    page: Page,
    city_name: str,
    selectors: LocationSelectors,
    config: RegionFlowConfig,
) -> None:
    """Handle city dropdown selection (SA, EG, ZA).

    These regions don't use postcodes but rather select a city from a predefined list.
    """
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_selector(selectors.location_display_line1, timeout=25000)
    await page.evaluate("document.body.style.zoom = '50%'")

    # Click location trigger
    trigger = await page.locator(selectors.location_trigger).first
    await trigger.click()

    # Click city dropdown button
    city_btn = await page.wait_for_selector(selectors.city_button_trigger, timeout=10000)
    await city_btn.click()

    # Select city from dropdown
    city_stripped = city_name.strip()
    if city_stripped in config.city_mapping:
        city_index = config.city_mapping[city_stripped]
        city_option_selector = f"{selectors.city_dropdown_option_prefix}{city_index}"
        city_option = await page.wait_for_selector(city_option_selector, timeout=10000)
        await city_option.click()
        logger.info(f"Selected city: {city_stripped} (index {city_index})")
    else:
        valid_cities = ", ".join(sorted(config.city_mapping.keys()))
        raise ValueError(
            f"City '{city_stripped}' not found in {config.region} city list. "
            f"Valid cities: {valid_cities}"
        )

    await page.wait_for_timeout(3000)


async def _setup_city_text_input(
    page: Page,
    city_name: str,
    selectors: LocationSelectors,
    config: RegionFlowConfig,
) -> None:
    """Handle city text input (AE).

    The AE region allows free-form city name entry but validates against a known list.
    """
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_selector(selectors.location_display_line1, timeout=25000)
    await page.evaluate("document.body.style.zoom = '50%'")

    city_stripped = city_name.strip()
    if city_stripped not in config.city_mapping:
        valid_cities = ", ".join(sorted(config.city_mapping.keys()))
        raise ValueError(
            f"City '{city_stripped}' not valid for {config.region}. "
            f"Valid cities: {valid_cities}"
        )

    # Click location trigger
    trigger = await page.locator(selectors.location_trigger).first
    await trigger.click()

    # Enter city name
    city_input = await page.wait_for_selector(selectors.city_input, timeout=10000)
    await city_input.fill("")
    await city_input.fill(city_stripped)

    # Click apply button
    apply_btn = await page.wait_for_selector(selectors.apply_button, timeout=10000)
    await apply_btn.click()
    # AE requires double-click in some implementations
    await apply_btn.click()

    await page.wait_for_timeout(3000)


def normalize_region(region: str) -> str:
    """Normalize region code to uppercase.

    Args:
        region: Region code

    Returns:
        Normalized region code
    """
    return str(region).strip().upper()


def normalize_keyword(keyword: str) -> str:
    """Normalize keyword to lowercase with collapsed whitespace.

    Args:
        keyword: Search keyword

    Returns:
        Normalized keyword
    """
    return " ".join(str(keyword).split()).lower()


def build_composite_key(keyword: str, region: str, sort: str) -> str:
    """Build composite key for checkpoint tracking.

    Args:
        keyword: Search keyword
        region: Region code
        sort: Sort type

    Returns:
        Composite key string
    """
    return f"{normalize_keyword(keyword)}_{normalize_region(region)}_{sort.lower()}"


def get_supported_regions() -> List[str]:
    """Get list of all supported region codes.

    Returns:
        Sorted list of two-letter region codes
    """
    return sorted(REGION_FLOWS.keys())


def get_region_config(region: str) -> RegionFlowConfig:
    """Get flow configuration for a region.

    Args:
        region: Two-letter region code

    Returns:
        RegionFlowConfig instance

    Raises:
        ValueError: If region is not supported
    """
    region_upper = region.upper()
    if region_upper not in REGION_FLOWS:
        raise ValueError(
            f"Unsupported region: {region}. "
            f"Supported: {', '.join(get_supported_regions())}"
        )
    return REGION_FLOWS[region_upper]
