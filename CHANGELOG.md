# Changelog

## 1.0.1 - 2026-10-10

- Export portable, content-addressed dossier evidence and validate it after a
  directory move or evidence deletion.
- Separate dossier format compatibility, locked V4.1 tool verification and
  the still-required scientific admission review.
- Fix bounded disk accounting so pre-existing workdir bytes are not charged
  again.
- Add lawful allow-listed full-text retrieval and exact line-region claim
  verification.
- Add a strict host hypothesis contract requiring three materially distinct
  candidates and actual actor/model provenance.
- Add the audited `text_delta` non-CSV plugin with preregistration, limits,
  retained outputs and tamper checks.
- Add runtime capability status reporting, CLI commands, CI and verification
  documentation.
