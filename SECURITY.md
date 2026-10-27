# Security and secrets handling

This is an educational prototype using synthetic capstone data. It is not approved for real customer information or production authentication.

## Do not publish

- `.env` files, API keys, access tokens, passwords, session cookies, or provider request headers.
- The extracted challenge dataset unless the course license and submission rules explicitly allow redistribution.
- Local audio recordings, generated response audio, runtime logs, cached indexes, or records containing personal information.

The repository `.gitignore` excludes these categories by default. Always inspect `git status --short` and `git diff --cached --name-only` before pushing.

## If a credential is exposed

Revoke or rotate it with its provider immediately, update the local `.env`, and check the Git history. Removing a key from the latest version does not remove it from past commits. Do not post the credential in an issue or chat.

## Scope limitations

The supplied order proof (phone suffix or delivery pincode) is appropriate only for the synthetic challenge dataset. It is not production-grade identity verification. Ticket creation saves a record but does not prove a live human agent has accepted, reviewed, or resolved it. Conversation state is in process memory and is not durable across restarts.

For suspected vulnerabilities in this student project, contact the project maintainer privately rather than posting credentials or real customer details in a public issue.


The five files explicitly included under `sample_audio/` are synthetic capstone test fixtures and are intentionally bundled. Other local audio files and all generated reply audio remain ignored by Git. Do not add real customer recordings or recordings of other people without appropriate permission.
