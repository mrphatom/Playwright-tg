import pytest

from platform_contracts import DeliveryTarget, GreyRequest, Platform


def test_discord_dm_request_uses_canonical_owner_and_round_trips_delivery_target():
    request = GreyRequest(
        platform=Platform.DISCORD,
        owner_user_id=6411860985,
        conversation_id=6411860985,
        text="  Check https://example.com  ",
        private=True,
        source_message_id="discord-message-1",
    )
    target = DeliveryTarget.discord_dm(owner_user_id=6411860985, channel_id=987654321)

    assert request.text == "Check https://example.com"
    assert request.conversation_id == 6411860985
    assert DeliveryTarget.from_dict(target.to_dict()) == target
    assert "token" not in target.to_dict()


def test_discord_guild_target_is_explicitly_non_private_and_channel_scoped():
    target = DeliveryTarget.discord_guild(owner_user_id=42, guild_id=100, channel_id=200)

    assert target.platform is Platform.DISCORD
    assert target.private is False
    assert target.guild_id == 100
    assert target.channel_id == 200


def test_delivery_target_rejects_missing_owner_or_ambiguous_discord_scope():
    with pytest.raises(ValueError, match="owner_user_id"):
        DeliveryTarget(platform=Platform.DISCORD, owner_user_id=0, conversation_id=1, private=True)
    with pytest.raises(ValueError, match="channel_id"):
        DeliveryTarget(platform=Platform.DISCORD, owner_user_id=42, conversation_id=1, private=False)


def test_request_rejects_empty_or_oversized_untrusted_text():
    with pytest.raises(ValueError, match="text"):
        GreyRequest(platform=Platform.DISCORD, owner_user_id=42, conversation_id=42, text=" ", private=True)
    with pytest.raises(ValueError, match="text"):
        GreyRequest(platform=Platform.DISCORD, owner_user_id=42, conversation_id=42, text="x" * 4001, private=True)
