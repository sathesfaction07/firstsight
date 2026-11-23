"""Selector configuration for marketplace delivery location controls.

These selectors are site-specific and should be overridden in deployment
configuration. The defaults shown here are plausible generic examples for
demonstration purposes only.
"""

from dataclasses import dataclass


@dataclass
class LocationSelectors:
    """CSS selectors for delivery location UI elements.

    All selectors must be overridden with site-specific values in production.
    The defaults are generic placeholders for portfolio demonstration.
    """

    # Main location display/trigger element
    location_trigger: str = "#delivery-location-trigger"
    location_display_line1: str = "#delivery-location-line1"
    location_display_line2: str = "#delivery-location-line2"

    # Postcode input controls
    postcode_input: str = "#location-postcode-input"
    postcode_input_part1: str = "#location-postcode-input-1"
    postcode_input_part2: str = "#location-postcode-input-2"

    # City/district selection
    city_input: str = "#location-city-input"
    city_button_trigger: str = "#location-city-button"
    city_dropdown_option_prefix: str = "#location-city-list-"

    # Country selection
    country_selector: str = "#location-country-selector"

    # Action buttons
    confirm_button: str = "#location-confirm-button"
    apply_button: str = "#location-apply-button"
    close_button: str = ".location-modal-close"
    dismiss_button: str = ".location-notification-dismiss"

    # Cookie consent (common on EU sites)
    cookie_accept: str = "#cookie-consent-accept"

    # Popover container
    popover_trigger: str = "#delivery-location-popover-trigger"

    # Country/region redirect
    redirect_confirm: str = "#region-redirect-confirm"


# Default instance - override these in your deployment configuration
DEFAULT_SELECTORS = LocationSelectors()
