# Batch Add Expiration Policy

This Azure API Management (APIM) policy ensures every Batch API request includes `output_expires_after` and `anchor` values when they are omitted by the caller. The policy defaults to a two-week expiration window anchored to the batch creation time.

## Behaviour

- Adds `output_expires_after` with `{"seconds": 1209600}` if the property is missing or null.
- Adds `anchor` with the value `created_at` if the property is missing or null.
- Leaves existing `output_expires_after` or `anchor` values untouched.

## Usage

1. Import `policy.xml` into the inbound policy section of the APIM operation that fronts the Batch API.
2. Replace `{backend-id}` with the identifier of your backend service or remove the element if set elsewhere.
3. Apply the policy to batch creation requests (for example, `POST /openai/v1/batches`).

## Testing

Send a batch request without `output_expires_after` or `anchor`. The backend receives the payload with both defaults added.
