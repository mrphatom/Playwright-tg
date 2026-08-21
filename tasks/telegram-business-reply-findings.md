# Telegram Business Reply Findings

Retrieved 2026-08-21 from official Telegram sources.

## Sources

- https://core.telegram.org/api/bots/connected-business-bots
- https://core.telegram.org/bots/api

## Relevant behavior

Telegram’s connected-business-bots documentation defines the MTProto update constructor `updateBotNewBusinessMessage` with both `message` and an optional top-level `reply_to_message` field:

`updateBotNewBusinessMessage ... connection_id: string message: Message reply_to_message: flags .0? Message ...`

The Bot API documentation defines `Update.business_message` as a `Message` update. The Bot API `Message` object also has a `reply_to_message` field for replies in the same chat/thread. The deployed implementation currently extracts only `business_message.reply_to_message`; therefore the user screenshot may indicate that Telegram’s business update exposes the replied-to message at the update level, or that the Python wrapper does not map the business-specific reply field onto the nested Message object. The fix should inspect both `update.reply_to_message` and `message.reply_to_message`, and use the update-level value first for Business Mode.

Telegram’s connected-business-bots documentation also states that business bots receive new business-message updates through the business connection and that reply/send operations use the connection ID.
