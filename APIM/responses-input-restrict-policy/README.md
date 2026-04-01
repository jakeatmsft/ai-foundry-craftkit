# Responses Tool Restrict Policy

This Azure API Management (APIM) policy enforces inline-file-only access for OpenAI traffic. It rejects file uploads via `POST .../files` and restricts `POST .../responses` to inline encoded file input (`file_data`) only.

For `POST .../responses`, if any of the following conditions is met the request is rejected with HTTP 400 `Request not allowed`:

- Any `input_file`/`file_input` item in `input` references uploaded files via `file_id` or non-empty `file_ids`.
- Any `input_file`/`file_input` item in `input` includes `file_url`.
- Any `input_file`/`file_input` item in `input` omits `file_data` or uses an empty `file_data`.
- Any attachment (or attachment tool) includes `file_id` or non-empty `file_ids`.
- Top-level `file_ids` is present and non-empty.
- The `background` property is present and evaluates to `true` (boolean or string).

For `POST .../files`, the request is rejected with HTTP 400 `Request not allowed`.

Inline encoded file input using non-empty `file_data` (for example Base64 payloads) is allowed.

When multiple conditions are violated the response message includes all relevant warnings.

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

The request above is rejected (HTTP 400) because the `input_file` item references `file_id`.

A request using `file_url` is also rejected:

```http
POST /your-operation HTTP/1.1
Content-Type: application/json

{
  "input": [
    {
      "content": [
        { "type": "input_text", "text": "Analyze this file." },
        { "type": "input_file", "file_url": "https://example.com/file.pdf" }
      ]
    }
  ]
}
```


To confirm the background guard, send a request with `"background": true`; the policy returns HTTP 400 with the message `Background requests are not permitted.`.

An example request that passes validation with Base64-encoded file input looks like this:

```http
POST /your-operation HTTP/1.1
Content-Type: application/json

{
  "input": [
    {
      "content": [
        { "type": "input_text", "text": "hello" },
        {
          "type": "input_file",
          "filename": "note.txt",
          "file_data": "data:text/plain;base64,SGVsbG8="
        }
      ]
    }
  ],
  "background": false
}
```

This request is forwarded to the backend because `input_file` uses inline `file_data` (Base64) and does not include `file_id`/`file_ids`, and `background` is `false`.
