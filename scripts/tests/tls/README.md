These public test certificates come from the [eMudhra incident disclosure](https://emudhra.we-have-a-problem.com/):

- `compromised-roots.pem` contains the four certificates in `roots.json`.
- The two chain files come from `chains.zip` and cover the emSign and AAA cross-signed paths.

Retrieved on October 21, 2026. Offline verification fixes the time to October 21, 2026, at 00:00 UTC so certificate expiration cannot masquerade as distrust. Each chain must verify against the deliberately vulnerable fixture and fail with an issuer error against patched certifi.
