## Antigravity CLI setup

1. Install the Antigravity CLI: (pending official distribution method).
2. Authenticate with your Anthropic account.
3. Verify headless operation with test invocations.

### Windows note

On Windows, transcript paths use POSIX-style `/Users/...` which resolve relative to the active drive.
The executor ensures dispatch runs with cwd on the system drive (typically C:) so paths resolve correctly.
