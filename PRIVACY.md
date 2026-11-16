# Privacy policy: numcheck hosted MCP server

Last updated: 16 November 2026

numcheck is an open-source tool (MIT) by Joona Lorenz. This policy covers the
hosted MCP server that ChatGPT and other assistants call when you use the
numcheck plugin. Running numcheck yourself sends nothing anywhere.

**What the server receives.** The text, PubMed Central ID or document URL that
the assistant passes to a numcheck tool. For a URL or PMCID the server
downloads that public document itself.

**What it does with it.** It checks the numbers in memory and returns the
result. Documents and results are not stored, not logged, not shared and not
used for training. Temporary files are deleted as soon as a request finishes.

**Logs.** The hosting provider and the server keep standard request logs
(time, path, status code, IP address) for operation and abuse prevention.
These logs contain no document content and are kept for at most 30 days.

**No accounts, no cookies, no tracking.**

**Confidential documents.** Do not send documents you are not allowed to share
with a third-party service. For confidential reports, run numcheck locally:
https://github.com/joonalorenz-commits/numcheck

**Contact.** Questions and deletion requests: open an issue at
https://github.com/joonalorenz-commits/numcheck/issues
