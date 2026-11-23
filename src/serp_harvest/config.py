"""Configuration settings for SerpHarvest."""

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(env_prefix="SH_", env_file=".env", extra="ignore")

    input_path: str = Field(default="data/sample_keywords.csv")
    output_path: str = Field(default="output/harvest.csv")
    base_url: str = Field(default="https://shop.example.com/search?q={keyword}&sort={sort}")
    max_concurrent: int = Field(default=8, ge=1, le=20)
    checkpoint_dir: str = Field(default=".checkpoints")
    checkpoint_every: int = Field(default=25, ge=1)
    resume: bool = Field(default=True)
    sink: Literal["local", "dynamodb", "both"] = Field(default="local")
    dynamodb_table_name: str = Field(default="product-harvest")
    dynamodb_region: str = Field(default="us-east-1")
    log_level: str = Field(default="INFO")
    user_name: str = Field(default="user")
    headless: bool = Field(default=True)

    @property
    def checkpoint_path(self) -> str:
        return os.path.join(self.checkpoint_dir, "checkpoint.json")


POSTCODE_MAP = {
    "US": "10001",
    "CA": "A1A 1A1",
    "UK": "EC1A 1BB",
    "SG": "238859",
    "AU": "2000",
    "DE": "10117",
    "FR": "75001",
    "IT": "00042",
    "IE": "D04 V2N1",
    "ES": "28001",
    "AE": "Dubai",
    "SA": "Riyadh",
    "ZA": "2196",
    "BR": "01319 900",
    "JP": "101 0025",
    "SE": "111 64",
    "BE": "1050",
    "TR": "34912",
    "MX": "11000",
    "NL": "1079",
    "PL": "00 277",
    "EG": "New Cairo",
    "IN": "400001",
}

SORT_TYPES = ["featured", "newest"]

REGIONS = list(POSTCODE_MAP.keys())
