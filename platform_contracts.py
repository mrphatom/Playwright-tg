"""Small platform-neutral contracts shared by Telegram and Discord adapters."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

MAX_REQUEST_TEXT = 4000


class Platform(StrEnum):
    TELEGRAM = "telegram"
    DISCORD = "discord"


@dataclass(frozen=True, slots=True)
class GreyRequest:
    platform: Platform
    owner_user_id: int
    conversation_id: int
    text: str
    private: bool
    source_message_id: str | None = None

    def __post_init__(self) -> None:
        if int(self.owner_user_id) <= 0:
            raise ValueError("owner_user_id must be positive")
        if int(self.conversation_id) <= 0:
            raise ValueError("conversation_id must be positive")
        normalized = str(self.text or "").strip()
        if not normalized or len(normalized) > MAX_REQUEST_TEXT:
            raise ValueError("text must be between 1 and 4000 characters")
        object.__setattr__(self, "owner_user_id", int(self.owner_user_id))
        object.__setattr__(self, "conversation_id", int(self.conversation_id))
        object.__setattr__(self, "text", normalized)
        object.__setattr__(self, "private", bool(self.private))
        if self.source_message_id is not None:
            object.__setattr__(self, "source_message_id", str(self.source_message_id)[:120])


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    platform: Platform
    owner_user_id: int
    conversation_id: int
    private: bool
    guild_id: int | None = None
    channel_id: int | None = None

    def __post_init__(self) -> None:
        if int(self.owner_user_id) <= 0:
            raise ValueError("owner_user_id must be positive")
        if int(self.conversation_id) <= 0:
            raise ValueError("conversation_id must be positive")
        if self.platform is Platform.DISCORD:
            if self.private and self.guild_id is not None:
                raise ValueError("private Discord targets cannot include guild_id")
            if not self.private and (self.guild_id is None or self.channel_id is None):
                raise ValueError("guild Discord targets require guild_id and channel_id")
        object.__setattr__(self, "owner_user_id", int(self.owner_user_id))
        object.__setattr__(self, "conversation_id", int(self.conversation_id))
        if self.guild_id is not None:
            object.__setattr__(self, "guild_id", int(self.guild_id))
        if self.channel_id is not None:
            object.__setattr__(self, "channel_id", int(self.channel_id))

    @classmethod
    def discord_dm(cls, owner_user_id: int, channel_id: int) -> "DeliveryTarget":
        return cls(Platform.DISCORD, owner_user_id, owner_user_id, True, channel_id=int(channel_id))

    @classmethod
    def discord_guild(cls, owner_user_id: int, guild_id: int, channel_id: int) -> "DeliveryTarget":
        return cls(Platform.DISCORD, owner_user_id, channel_id, False, guild_id=int(guild_id), channel_id=int(channel_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform.value,
            "owner_user_id": self.owner_user_id,
            "conversation_id": self.conversation_id,
            "private": self.private,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DeliveryTarget":
        if not isinstance(value, dict):
            raise ValueError("delivery target must be an object")
        try:
            platform = Platform(str(value["platform"]))
            return cls(
                platform=platform,
                owner_user_id=int(value["owner_user_id"]),
                conversation_id=int(value["conversation_id"]),
                private=bool(value["private"]),
                guild_id=int(value["guild_id"]) if value.get("guild_id") is not None else None,
                channel_id=int(value["channel_id"]) if value.get("channel_id") is not None else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid delivery target") from exc
