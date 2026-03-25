# OpenAI Responses Prompt Cache Key Plan

## Summary

This plan adds a stable `prompt_cache_key` for OpenClaw sessions that use the OpenAI Responses API.

The immediate target is the user's `sub2api` setup:

```json
{
  "baseUrl": "https://sub2api.recodex.top/v1",
  "api": "openai-responses",
  "model": "sub2api/gpt-5.4"
}
```

`sub2api` is an OpenAI-compatible relay that forwards requests to OpenAI. Today OpenClaw strips `prompt_cache_key` for non-direct Responses endpoints, so this setup cannot benefit from session-level cache routing even when the upstream provider supports it.

## Problem

OpenClaw already does useful prompt-stability work:

- stable system prompt after warmup for normal turns
- dynamic inbound metadata moved out of the system prompt
- stable session identity via `sessionId`

But it does not currently generate a session-scoped `prompt_cache_key`.

For OpenAI Responses payloads, the current behavior is:

- keep user-supplied `prompt_cache_key` only for direct OpenAI and Azure OpenAI endpoints
- strip `prompt_cache_key` for custom OpenAI-compatible endpoints

That means a long-lived Telegram conversation routed through `sub2api` cannot use a stable session key to improve prefix cache hit rate.

## Goal

For any session using `api: "openai-responses"`, automatically attach a stable `prompt_cache_key` derived from the current OpenClaw `sessionId`, unless the caller explicitly set one.

Desired behavior:

- same session: same `prompt_cache_key`
- `/new`, `/reset`, or session rollover: new `sessionId`, so new `prompt_cache_key`
- explicit `prompt_cache_key` from config or caller override always wins
- non-Responses APIs remain unchanged

## Non-goals

- no prompt restructuring
- no bootstrap/delta transcript redesign
- no transport-specific append redesign
- no change to Anthropic cache retention behavior
- no new public config surface unless follow-up work proves it is needed

## Why This Is The Smallest Useful Change

OpenClaw already has the required building blocks:

- `src/auto-reply/reply/session.ts` reuses `sessionId` for fresh sessions
- `src/agents/pi-embedded-runner/run/attempt.ts` already threads run-scoped data into the embedded runner wrappers
- `src/agents/pi-embedded-runner/openai-stream-wrappers.ts` already patches Responses payloads through `onPayload`

So the plan only needs to:

1. pass a stable session-scoped default key into the payload patch chain
2. inject it into Responses payloads when no explicit key exists
3. stop stripping it for OpenAI-compatible Responses relays such as `sub2api`

## Proposed Behavior

### Before

- direct OpenAI/Azure Responses:
  - preserve `prompt_cache_key` if the caller already supplied one
  - do not auto-generate one
- custom OpenAI-compatible Responses endpoints:
  - strip `prompt_cache_key`

### After

- all `openai-responses` endpoints:
  - if payload already contains `prompt_cache_key`, preserve it
  - otherwise inject `prompt_cache_key = sessionId`
- all non-Responses APIs:
  - unchanged

## Design

### 1. Source Of Truth

Use the existing OpenClaw `sessionId` as the default `prompt_cache_key`.

Reasoning:

- it is already stable for an existing conversation
- it naturally changes on reset or rollover
- it is narrower and more cache-friendly than user-level or channel-level keys

### 2. Injection Point

Use the existing Responses payload patch path in `src/agents/pi-embedded-runner/openai-stream-wrappers.ts`.

Do not rely on generic extra params passthrough alone. The current extra params pipeline mostly maps to stream options such as:

- `temperature`
- `maxTokens`
- `transport`
- `openaiWsWarmup`
- `cacheRetention`

It does not automatically place arbitrary keys into the OpenAI Responses payload.

### 3. Internal Default Field

Add an internal-only field in the embedded runner path for the default cache key.

Suggested name:

```ts
sessionPromptCacheKey
```

Rules:

- internal only
- not documented as a user-facing generic model param
- used only as a fallback when `prompt_cache_key` is absent

### 4. Resolution Order

When constructing a Responses payload:

1. if payload already has `prompt_cache_key`, keep it
2. else if extra params include explicit `prompt_cache_key` or `promptCacheKey`, use that
3. else if internal `sessionPromptCacheKey` exists, use that
4. else omit the field

This preserves operator intent while giving sessions a useful default.

### 5. Endpoint Policy

Treat any `api: "openai-responses"` endpoint as eligible.

Rationale:

- the user's main case is an OpenAI-compatible relay
- this is a compatibility choice, not a trust or security boundary
- if a relay ignores the field, behavior remains correct and only the optimization is lost

If a future compatibility issue appears for a specific relay, add a narrow opt-out later. Do not block the default implementation on speculative incompatibility.

## File-Level Plan

### `src/agents/pi-embedded-runner/run/attempt.ts`

- pass `sessionPromptCacheKey: params.sessionId` into the extra params flow
- keep it internal to the embedded runner path

### `src/agents/pi-embedded-runner/extra-params.ts`

- allow the internal default cache-key field to remain available to downstream payload wrappers
- do not expose it as a documented generic stream option

### `src/agents/pi-embedded-runner/openai-stream-wrappers.ts`

- add a helper to resolve the effective prompt cache key
- inject `prompt_cache_key` into Responses payloads when absent
- remove or relax the current "non-direct endpoint strips prompt cache fields" rule
- preserve existing behavior for:
  - `store`
  - `context_management`
  - `service_tier`
  - `fastMode`

### `src/agents/pi-embedded-runner-extraparams.test.ts`

- add coverage for session-key injection
- update the current non-direct stripping expectations

### `src/agents/openai-ws-stream.test.ts`

- verify the final `response.create` payload can carry `prompt_cache_key` through the existing `onPayload` patch path

## Testing Plan

### Unit tests

Add or update tests for:

- direct OpenAI Responses injects `sessionPromptCacheKey` when no explicit key exists
- Azure OpenAI Responses injects `sessionPromptCacheKey` when no explicit key exists
- custom Responses endpoint such as `sub2api` injects `sessionPromptCacheKey` when no explicit key exists
- explicit `prompt_cache_key` is preserved and not overwritten by `sessionId`
- non-Responses APIs do not gain `prompt_cache_key`

### WebSocket coverage

Verify that the Responses WebSocket path still sends:

- `instructions`
- `previous_response_id` when applicable
- injected `prompt_cache_key` via the payload patch chain

### Manual verification

With the user's `sub2api/gpt-5.4` config:

1. start a fresh Telegram session
2. inspect the first Responses payload
3. confirm `prompt_cache_key` matches OpenClaw `sessionId`
4. send a second message in the same session
5. confirm `prompt_cache_key` stays the same
6. run `/new` or `/reset`
7. confirm the next request uses a different key

## Rollout Checks

Expected positive signals:

- stable `prompt_cache_key` across turns in one session
- upstream usage begins to show more cached input tokens
- no regression for non-Responses providers

Potential failure modes:

- a relay rejects unknown fields in the Responses payload
- an internal wrapper accidentally drops the field after injection
- explicit operator-provided `prompt_cache_key` gets overwritten

Rollback is straightforward:

- disable the new injection logic
- restore the previous stripping rule for non-direct endpoints

## Future Follow-ups

Not part of this change, but worth tracking:

- optional per-model opt-out if a specific relay is incompatible
- optional user-facing `prompt_cache_key` diagnostics in debug logs
- broader prompt cache optimization beyond key injection, such as reducing repeated body-side bootstrap content

## Implementation Checklist

- [ ] thread `sessionId` into the Responses payload patch chain as `sessionPromptCacheKey`
- [ ] resolve the effective prompt cache key with explicit override precedence
- [ ] inject `prompt_cache_key` for all `openai-responses` endpoints when absent
- [ ] stop stripping prompt cache fields for custom OpenAI-compatible Responses endpoints
- [ ] add unit coverage for direct, Azure, and `sub2api` cases
- [ ] add or update WebSocket payload coverage
- [ ] manually verify stable key reuse across two turns and reset behavior
