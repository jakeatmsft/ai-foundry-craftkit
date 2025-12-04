# Responses Model Restrict Policy

This Azure API Management (APIM) policy blocks calls made with disallowed `model` values. Requests that specify a restricted model (or omit the `model` property entirely) are rejected before reaching the backend.

## Behaviour

- Parses the inbound JSON body and reads the top-level `model` property.
- Compares the provided value (case insensitive) against the `restrictedModels` list defined in the policy.
- Rejects the call with HTTP 400 if the `model` is missing or matches an entry in the restricted list, returning a message that spells out the blocked models.
- Allows the request to proceed unchanged when the `model` value is not restricted.

## Usage

1. Import `policy.xml` into the inbound policy section of the APIM operation that fronts the Responses API.
2. Customize the `restrictedModels` array in the policy to match the models you want to block (defaults to `computer-use-preview`).
3. Optionally edit the rejection message if you want to provide additional guidance (for example, a support contact or internal ticket link).

## Testing

- Send a request with `"model": "gpt-4o-mini"`; the request continues to the backend because the model is not restricted.
- Send a request with `"model": "computer-use-preview"`; APIM returns HTTP 400 with a message similar to `Model 'computer-use-preview' is restricted. Restricted models: computer-use-preview.`
- Send a request that omits the `model` property; the policy responds with HTTP 400 `Model property is required.`
