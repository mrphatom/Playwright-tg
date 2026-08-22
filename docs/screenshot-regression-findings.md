# Screenshot regression findings

## Evidence reviewed

Reviewed `IMG_1144.PNG` and `IMG_1143.PNG` only after the user explicitly requested screenshot inspection. The screenshots show the same GreyAI Telegram response being viewed as a long, vertically scrolling code message. The visible content is a JavaScript MCP server example, including imports, server construction, tool schema, request handling, and error handling.

## Concrete observations

1. The long code answer appears as an ordinary Telegram message with no visible Previous/Next inline navigation controls.
2. The response is code-formatted and visually readable, but the user is forced to scroll through one very long message rather than navigate bounded pages.
3. The screenshots do not show a ZIP/document attachment for the code example; they show inline code only.
4. The surrounding user message says “Do it again,” which indicates a continuation/retry request, but the visible response does not show a compact operation receipt or a navigable result state.
5. No conclusion is drawn from the screenshots about hidden secrets because the visible portions do not establish whether the full message contains credentials. Source-level redaction and artifact tests must verify this independently.

## Investigation direction

The highest-probability causes are: a long code response bypassing `deliver_text_response`, application-generated HTML being treated as Markdown/plain text inconsistently, and the code-starter ZIP flow being available only for the dedicated Grey integration starter rather than for an authorized request to package generated code. The next steps are to inspect the remaining screenshots and then reproduce each path from source tests without sending Telegram messages as the user.

## Additional evidence reviewed

Reviewed `IMG_1142.PNG` and `IMG_1141.PNG`. The same long response continues through an MCP server implementation, then transitions into package configuration and deployment instructions. The message still has no visible Previous/Next controls. The code is presented in Telegram’s styled code blocks, while the surrounding prose and separators are mixed into the same long message. The screenshot itself does not prove a secret leak, but it confirms that the answer is being delivered as a single scroll-heavy response rather than as a bounded navigable result.

The code shown includes an SSE transport, an Express server, tool registration, request handling, and package files. This is a generated implementation answer, not visibly an attached `.zip` artifact. The response therefore needs two distinct supported outcomes: a navigable text explanation and, when the user requests packaging and the plan/role permits it, a validated code archive delivered as a Telegram document.

## Additional evidence reviewed

Reviewed `IMG_1140.PNG` and `IMG_1139.PNG`. `IMG_1140.PNG` shows the long code response continuing into deployment instructions, then a separate GreyAI provider-alert message appears immediately below it. `IMG_1139.PNG` reveals a distinct formatting/security regression in the developer API example: Telegram displays literal `<b>`, `<code>`, and `<pre><code>` tags instead of rendering them. The authorization example is also visibly corrupted as `Authorization=[redacted]` followed by escaped entity text, rather than a valid readable placeholder such as `Authorization: Bearer <developer_api_key>`.

This confirms that the developer API example is application-generated Telegram HTML being passed through the generic Markdown-to-HTML sanitizer and credential redactor as if it were raw Markdown. The fix must separate trusted application-generated Telegram HTML from ordinary untrusted text, apply targeted placeholder-safe redaction, and preserve Telegram formatting. Provider-alert interleaving should remain a separate operational notification, but it must not corrupt or replace the user’s result.

## Additional evidence reviewed

Reviewed `IMG_1138.PNG` and `IMG_1137.PNG`. The malformed API example continues to display literal closing tags such as `</code></pre>`, confirming the formatting problem affects the entire application-generated HTML response, not just the first paragraph.

`IMG_1137.PNG` confirms that the dedicated Grey Telegram integration starter does produce and deliver a `.zip` document (`greyai-telegram-integration.zip`, shown as 2.8 KB). Immediately afterward Grey returns a separate “Just a normal conversation it is!” message, suggesting the user’s “do it again” / follow-up flow can produce an unintended conversational fallback after the artifact operation. The ZIP path itself works for the dedicated starter, but this does not prove that arbitrary generated code can be packaged on request.

## Additional evidence reviewed

Reviewed `IMG_1136.PNG` and `IMG_1135.PNG`. These show a separate generated Python Telegram bot example, including a code line rendered as `TOKEN=[redacted]`, followed by a provider-recovered notification. The code is still part of a long ordinary message with no Previous/Next controls. The displayed token placeholder is safer than exposing a real token, but the line is syntactically damaged and no longer a copyable valid example.

The provider-recovered notice is operationally useful but visually interleaves with the user’s generated code flow. It should not alter the result, but Grey’s response pipeline should use a stable operation/result relationship so provider alerts do not look like the answer was interrupted or replaced.

## Additional evidence reviewed

Reviewed `IMG_1134.PNG` and `IMG_1133.PNG`. `IMG_1134.PNG` shows the dedicated ZIP delivery followed by multiple normal conversational responses, then a media-processing status message. The sequence appears noisy and does not visibly bind the replies to one stable operation or result.

`IMG_1133.PNG` shows the exact user request `Give a longer version` followed by a long ordinary chat answer beginning with a detailed MCP/Manus explanation. It is rendered as one scrollable message with no Previous/Next buttons. This is the core reproduction for the normal-chat long-output path, separate from the developer API-example formatting defect.

## Additional evidence reviewed

Reviewed `IMG_1132.PNG` and `IMG_1131.PNG`. The “Give a longer version” response continues through both Python and Node.js MCP implementation options in the same ordinary Telegram message. There are no Previous/Next controls, no attached code archive, and no visible result/operation boundary. The code is readable in places but is not presented as a downloadable project artifact.

The screenshots support separating three behaviors: explanatory long text should be paginated; a request to package the generated code should produce a validated ZIP; and a follow-up such as “do it again” should remain attached to the active task/result rather than falling through to a generic chat greeting.

## Final screenshot evidence reviewed

Reviewed `IMG_1130.PNG` and `IMG_1129.PNG`. The answer continues through the Python SSE implementation and into a separate Node.js/TypeScript implementation in the same long message. It ends without visible Previous/Next controls and without an explicit “package this code” action or attached archive for the generated MCP project.

The complete screenshot set therefore establishes four concrete regressions: application-generated HTML is escaped literally; credential redaction corrupts copyable example syntax; long normal-chat answers bypass or fail to expose navigation; and generated code is shown inline without an available generalized ZIP packaging path. The dedicated Grey integration starter ZIP is a separate working path and should be retained.
