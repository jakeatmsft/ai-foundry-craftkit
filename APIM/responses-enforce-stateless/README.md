# Responses Enforce Stateless Policy

This Azure API Management (APIM) policy forces stateless behaviour when calling the OpenAI Responses API. It strips any `previous_response_id` supplied by the caller and ensures `store` is always `false` so responses are not persisted by the service.

## Behaviour

- Removes `previous_response_id` from the JSON payload before forwarding to the backend.
- Adds (or overwrites) the top-level `store` property with `false`.
- Leaves the remaining request body untouched.

## Usage

1. Import `policy.xml` into the inbound policy section of the APIM operation that fronts the Responses API.
2. Replace `{backend-id}` with the identifier of your backend service or remove the element if set elsewhere.
3. Callers may include `previous_response_id` or `store` in their request, but the policy guarantees the backend receives neither history nor stored responses.

## Testing

Send a request that includes `"previous_response_id": "resp_123"` or `"store": true`; the backend receives a body identical to the original but without `previous_response_id` and with `"store": false`.
