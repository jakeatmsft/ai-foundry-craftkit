# Responses Tool Restrict Policy

This Azure API Management (APIM) policy blocks Responses tool invocations that attempt to upload files or run with `background` execution. It inspects the incoming request body, looks at the `input` array supplied to the tool invocation, and checks the top-level `background` flag.

If either of the following conditions is met the request is rejected with HTTP 400 `Request not allowed`:

- Any `content` item within `input` contains an object with `"type": "input_file"` (case-insensitive).
- The `background` property is present and evaluates to `true` (boolean or string).

When both conditions are violated the response message includes both warnings.

## Usage

1. Import `policy.xml` into the inbound policy section of the APIM operation or API that fronts the Responses tool.
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
