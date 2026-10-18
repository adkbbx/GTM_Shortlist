# Security reports

Send security reports to [Eygentic](mailto:hello@eygentic.com), with the subject "GTM Shortlist security report". This is the project's general contact address; no dedicated security response time is promised. Do not disclose exploitable details in a public issue.

Include the affected version or commit, reproduction steps using synthetic data, and the impact. Do not send provider keys, session tokens, private research databases or personal data. Revoke exposed credentials through their provider.

The local app trusts one operator and must stay on loopback. Do not expose it through a public tunnel or network binding. Windows provider storage uses current-user encryption. Other supported systems use owner-only file permissions. Backups and exports need the same care as the original research.

Hosted deployments have separate authentication, database-role and operational requirements. Their release checks are in [IMPLEMENTATION.md](docs/IMPLEMENTATION.md). A local sample run does not verify hosted security or live provider access.
