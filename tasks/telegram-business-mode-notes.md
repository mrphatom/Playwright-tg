# Telegram Business Mode implementation notes

Retrieved 2026-08-21 from official Telegram documentation.

## Sources

- https://core.telegram.org/bots/api — Telegram Bot API. The current documentation lists `business_connection`, `business_message`, `edited_business_message`, and `deleted_business_messages` as update types. Business messages are messages from a connected business account.
- https://core.telegram.org/api/business — Telegram Business documentation. Connected bots can process and answer messages on behalf of a user’s business account.
- https://docs.python-telegram-bot.org/en/v21.9/telegram.ext.businessconnectionhandler.html — python-telegram-bot documentation. `BusinessConnectionHandler` was added in v21.1 and handles `Update.business_connection`.

## Implementation conclusions

The repository currently pins python-telegram-bot 20.7, which does not expose business update fields or `BusinessConnectionHandler`. The working tree has been updated to pin 22.8, and the local virtual environment was upgraded to 22.8 for compatibility testing.

A normal Telegram bot cannot silently participate in arbitrary user-to-user private chats. The supported Bot API path for Mira-like visible separate replies is Telegram Business Mode: the owner connects GreyAI as a business bot, GreyAI receives `business_message` updates, and replies are sent with the message’s `business_connection_id`. The original user message remains visible because GreyAI sends a separate business reply rather than returning only an inline result.

The implementation must remain explicit and permission-scoped. It should store only the connection ID, owner user/chat IDs, enabled state, and read/reply rights. It must not process business messages unless the connection is enabled, the bot can read and reply, and the owner account is authorized. Business watcher notifications need the persisted connection ID so they can continue replying directly after restarts.
