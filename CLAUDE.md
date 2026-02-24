# CLAUDE.md

## Project Overview

**anthropic-proxy** is a lightweight proxy server that translates Anthropic API requests into OpenAI-compatible format and forwards them to OpenRouter.ai (or any OpenAI-compatible endpoint). This enables tools like Claude Code to work with alternative LLM backends.

## Tech Stack

- **Runtime**: Node.js (ES modules via `"type": "module"`)
- **Framework**: Fastify v5
- **Language**: Plain JavaScript (no TypeScript, no build step)
- **No test framework** — there are currently no tests

## Project Structure

```
anthropic-proxy/
├── index.js          # Entire application — single-file server
├── package.json      # Dependencies and metadata
├── package-lock.json # Locked dependency versions
├── README.md         # User-facing documentation
└── .gitignore        # Ignores node_modules/
```

This is a single-file application. All logic lives in `index.js`.

## Running the Project

```bash
# Install dependencies
npm install

# Start the server
npm start

# Or with environment variables
OPENROUTER_API_KEY=your-key PORT=3000 npm start

# Debug mode (verbose logging)
DEBUG=1 npm start
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes (unless custom base URL set) | — | OpenRouter API key |
| `ANTHROPIC_PROXY_BASE_URL` | No | `https://openrouter.ai/api` | Custom OpenAI-compatible API base URL |
| `PORT` | No | `3000` | Server listen port |
| `REASONING_MODEL` | No | `google/gemini-2.0-pro-exp-02-05:free` | Model used when `thinking` is enabled |
| `COMPLETION_MODEL` | No | `google/gemini-2.0-pro-exp-02-05:free` | Model used for standard completions |
| `DEBUG` | No | — | Set to `1` to enable verbose debug logging |

## Architecture

### API Endpoint

The server exposes a single POST endpoint: **`/v1/messages`** — mimics the Anthropic Messages API.

### Request Flow

1. **Receive** an Anthropic-format request on `/v1/messages`
2. **Transform** the payload to OpenAI chat completions format:
   - System messages extracted from `payload.system` array
   - User/assistant messages normalized (string or content-block arrays)
   - Tool use blocks (`tool_use`) mapped to OpenAI `tool_calls`
   - Tool results (`tool_result`) mapped to OpenAI `tool` role messages
   - Tool schemas have `format: 'uri'` stripped (via `removeUriFormat` helper)
   - The `BatchTool` tool name is filtered out
3. **Forward** to `{baseUrl}/v1/chat/completions`
4. **Transform response** back to Anthropic format:
   - **Non-streaming**: Full JSON response mapped to Anthropic message structure
   - **Streaming**: OpenAI SSE chunks translated to Anthropic SSE events

### Streaming Protocol

The streaming implementation translates OpenAI's SSE format to Anthropic's SSE event protocol:
- `message_start` — initial message metadata
- `ping` — keepalive
- `content_block_start` / `content_block_delta` / `content_block_stop` — text and tool use deltas
- `message_delta` — stop reason and final usage
- `message_stop` — end of stream

### Key Functions

- **`sendSSE(reply, event, data)`** — Writes an SSE event to the response stream
- **`mapStopReason(finishReason)`** — Maps OpenAI finish reasons to Anthropic stop reasons
- **`normalizeContent(content)`** — Normalizes string or array content blocks
- **`removeUriFormat(schema)`** — Recursively strips `format: 'uri'` from JSON schemas (compatibility fix)

## Code Conventions

- ES module syntax (`import`/`export`)
- No semicolons in most code (mixed style — some lines have them)
- Single quotes for strings (mostly)
- Fastify logger enabled by default
- No TypeScript, no linter, no formatter configured
- No test suite exists

## Common Tasks

### Adding a new endpoint
Add a new route handler using Fastify's routing API (e.g., `fastify.get(...)`) in `index.js`.

### Modifying the request/response translation
All translation logic is in the `/v1/messages` route handler in `index.js`. The request transformation builds the `openaiPayload` object; the response transformation happens in either the non-streaming JSON path or the streaming SSE reader loop.

### Debugging
Set `DEBUG=1` to enable the `debug()` logging function, which logs payloads and SSE chunks to stdout.

## Known Quirks

- The `removeUriFormat` helper exists because some downstream providers don't support `format: 'uri'` in JSON schemas.
- The `BatchTool` is explicitly filtered out from tools sent to the backend.
- Usage token counts fall back to word-count estimates when the upstream API doesn't provide token usage data.
- Tool call argument deltas are accumulated and diffed to produce incremental `input_json_delta` events.
