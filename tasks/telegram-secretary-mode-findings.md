# Telegram Secretary Mode diagnosis

Retrieved 2026-08-21 from official Telegram documentation.

- Telegram’s current official Bot Features documentation calls the connected-account capability **Secretary Mode** / **Secretary Bots**, not Business Mode in the user-facing BotFather UI.
- Official setup requires enabling Secretary Mode for the bot in @BotFather, handling BusinessConnection updates, processing business_message updates, checking can_reply, and using business_connection_id when sending on behalf of the account.
- Telegram’s Connected business bots API documentation confirms that connected bots receive business-connection updates and business-message updates, and that the connection ID is used to receive messages and send replies as the user.
- The current Bot API documentation lists Update.business_connection and Update.business_message fields.

Sources:
- https://core.telegram.org/bots/features
- https://core.telegram.org/api/bots/connected-business-bots
- https://core.telegram.org/bots/api

Diagnosis: the user’s screenshot is showing the correct Telegram feature. The red/off **Secretary Mode** switch is the setting that must be enabled; there may be no separate “Business Mode” label in the current client.
