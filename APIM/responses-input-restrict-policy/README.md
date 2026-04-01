# Responses Tool Restrict Policy

This Azure API Management (APIM) policy blocks restricted payload patterns only for `Responses API` create calls (`POST .../responses`). It inspects the incoming request body, looks at the `input` array, attachment/file references, and checks the top-level `background` flag.

Requests to other APIs such as `Chat Completions`, `Batch`, and `files.create` are not evaluated by this policy and pass through unchanged.

For `POST .../responses`, if either of the following conditions is met the request is rejected with HTTP 400 `Request not allowed`:

- Any `content` item within `input` contains an object with `"type": "input_file"` (case-insensitive).
- Any attachment (or attachment tool) includes `file_id` or non-empty `file_ids`.
- Top-level `file_ids` is present and non-empty.
- The `background` property is present and evaluates to `true` (boolean or string).

When both conditions are violated the response message includes both warnings.

## Usage

1. Import `policy.xml` into the inbound policy section of the APIM operation or API that fronts OpenAI traffic.
2. Make sure the operation forwards the request body unchanged so the policy can inspect the JSON payload.
3. Customise the error message by editing the `restrictionMessage` variable inside the policy if your scenario requires different guidance for callers.

## Testing

You can verify the behaviour with simple requests:

```http
POST /your-operation HTTP/1.1
Content-Type: application/json

{
  "input": [
    {
      "content": [
        { "type": "input_text", "text": "hello" },
        { "type": "input_file", "file_id": "file-123" }
      ]
    }
  ]
}
```

The request above is rejected (HTTP 400) because it contains `input_file`. A request without `input_file` and with `"background": false` is forwarded to the backend normally.


To confirm the background guard, send a request with `"background": true`; the policy returns HTTP 400 with the message `Background requests are not permitted.`.

An example request that passes validation looks like this:

```http
POST /your-operation HTTP/1.1
Content-Type: application/json

{
  "input": [
    {
      "content": [
        { "type": "input_text", "text": "hello" }
      ]
    }
  ],
  "background": false
}
```

This request is forwarded to the backend because it omits `input_file` and sets `background` to `false`.
