# Reading Engine v8: runtime configuration and offline verification

`READING_ENGINE` defaults to `legacy`. Setting it to `v8` selects the new
generator only for question, love and career three-card readings. Daily card,
full spread and Moon chat keep the legacy behavior and Google credentials.

Use the standard `OPENAI_API_KEY`. `OPENAI_MODEL` defaults to `gpt-5.6-terra`.
The OpenAI SDK is the default transport. `OPENAI_TRANSPORT=curl` optionally
selects curl and requires its executable and Unix `/dev/fd` support. Both
transports disable retries and redirects. Preserve the deployment's proxy and
CA settings; never put credentials into tracked configuration or logs.

Start from the repository directory so `cards/` and the existing history and
analytics paths resolve correctly. The existing server entry point is
`/root/moon-mentor-bot/main.py` under `moon-mentor.service`; this release does not
change its service configuration or existing state files.

For a separate verification environment, install the runtime requirements with
the tested server constraints, then run the offline suite:

```sh
python -m venv /tmp/moon-v8-check
/tmp/moon-v8-check/bin/python -m pip install -r requirements.txt -c requirements-server-test.txt
/tmp/moon-v8-check/bin/python -B run_tests_offline.py
```

The suite imports real aiogram and google-genai, but blocks socket connections,
real subprocesses and polling. It substitutes model and Telegram responses.
The runtime requirements do not require OpenAI 3.x; the verified SDK is 2.44.0.

Deduplication and successful response caching last for the lifetime of one
process. They are not durable across restarts or shared between workers. Errors
do not trigger another model or legacy fallback. A timeout does not prove that
the provider did not process the request. Switching to `legacy` affects new
operations; already cached v8 operations retain their original result.

Optional Telegram Stars accounting adds a persistent credit ledger and durable
successful results when `PAYMENTS_ENABLED=true`; see `PAYMENTS_MVP.md`. It is
disabled by default and does not alter the unmetered legacy path.
