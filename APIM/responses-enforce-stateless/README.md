# Responses Enforce Stateless Policy

This Azure API Management (APIM) policy forces stateless behaviour when calling the OpenAI Responses API. It strips any `previous_response_id` supplied by the caller, ensures `store` is always `false` so responses are not persisted by the service, and removes any attempt to run background tasks.

## Behaviour

- Removes `previous_response_id` from the JSON payload before forwarding to the backend.
- Adds (or overwrites) the top-level `store` property with `false`.
- Removes the top-level `background` property to block asynchronous background execution.
- Leaves the remaining request body untouched.

## Usage

1. Import `policy.xml` into the inbound policy section of the APIM operation that fronts the Responses API.
2. Replace `{backend-id}` with the identifier of your backend service or remove the element if set elsewhere.
3. Callers may include `previous_response_id`, `store`, or `background` in their request, but the policy guarantees the backend receives neither history nor stored responses nor background task requests.

## Testing

Send a request that includes `"previous_response_id": "resp_123"`, `"store": true`, or `"background": true`; the backend receives a body identical to the original but without `previous_response_id`, with `"store": false`, and with the `background` property removed.
