"""Validated application configuration loaded from YAML and environment."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PositiveFloat, PositiveInt, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_directory: Path = Path("var/raw")
    manifest_directory: Path = Path("var/manifests")


class HttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connect_timeout_seconds: PositiveFloat = 15
    read_timeout_seconds: PositiveFloat = 120
    retries: int = Field(default=3, ge=0, le=10)
    user_agent: str = "earthquake-ontology/0.1"


class DirectDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["direct"]
    url: HttpUrl
    period: str = "current"


class HtmlLinksDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["html_links"]
    index_url: HttpUrl
    link_pattern: str

    @field_validator("link_pattern")
    @classmethod
    def require_period_group(cls, value: str) -> str:
        import re
        if "period" not in re.compile(value).groupindex:
            raise ValueError("link_pattern must define a named 'period' group")
        return value


class FdsnYearlyDiscovery(BaseModel):
    """Generate reproducible one-year FDSN event queries."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["fdsn_yearly"]
    endpoint: HttpUrl
    start_year: int = Field(ge=1800, le=2200)
    end_year: int | Literal["current"] = "current"
    minimum_magnitude: float | None = Field(default=None, ge=-2, le=10)
    catalog: str | None = None

    @field_validator("end_year")
    @classmethod
    def valid_end_year(cls, value, info):
        start = info.data.get("start_year")
        if isinstance(value, int) and start is not None and value < start:
            raise ValueError("end_year must not be before start_year")
        return value


DiscoveryConfig = Annotated[Union[DirectDiscovery, HtmlLinksDiscovery, FdsnYearlyDiscovery], Field(discriminator="type")]


class BasicAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["basic"]
    username_env: str
    password_env: str


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    provider: str
    dataset_uri: HttpUrl
    discovery: DiscoveryConfig
    destination_name: str
    media_type: str
    parser: str | None = None
    auth: BasicAuthConfig | None = None
    license_url: HttpUrl | None = None

    @field_validator("destination_name")
    @classmethod
    def safe_destination(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("destination_name must be a file name template, not a path")
        try:
            value.format(period="period")
        except (KeyError, ValueError) as exc:
            raise ValueError("destination_name may only use the {period} field") from exc
        return value


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid",
        env_prefix="EQ_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )
    storage: StorageConfig = StorageConfig()
    http: HttpConfig = HttpConfig()
    sources: dict[str, SourceConfig]


def load_settings(path: Path) -> AppSettings:
    """Load YAML with environment variables taking precedence over the file."""
    config_path = path.resolve()

    class YamlSettings(AppSettings):
        model_config = SettingsConfigDict(
            **(
                AppSettings.model_config
                | {"yaml_file": config_path, "yaml_file_encoding": "utf-8"}
            )
        )

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (
                init_settings,
                env_settings,
                YamlConfigSettingsSource(settings_cls),
                file_secret_settings,
            )

    return YamlSettings()
