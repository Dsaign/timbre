# 08: Feedback

**What to build:** the visitor can vote 👍 or 👎 on each Match, switch the vote, or press the same thumb again to withdraw it. The vote survives a reload. A short notice explains that Descriptions and votes are stored to improve the model. Nothing stored identifies the visitor.

**Blocked by:** 04

**Status:** resolved

- [x] The `feedback` schema stores votes with: normalized Description, Song ID, vote, timestamps and a salted visitor hash. The IP-hash salt is a secret.
- [x] A Feedback endpoint takes a Description, a Song ID and a vote: up, down, or none (withdraw). There is one vote per (visitor hash, normalized Description, Song), and the latest wins.
- [x] Descriptions are normalized as: Unicode NFC, trimmed, whitespace collapsed, lowercased.
- [x] Search responses include the visitor's current vote for each Match.
- [x] A daily timer in the API process clears visitor hashes older than 7 days (the hash becomes null) and keeps the vote.
- [x] Front: 👍/👎 on each card, with the current vote highlighted. Pressing the other thumb switches the vote, and pressing the same thumb withdraws it. Updates are optimistic and reverted on error. Both buttons are labelled and keyboard-reachable.
- [x] A privacy notice under the search box says that Descriptions and votes are stored to improve the model.
- [x] API tests cover upsert, switch, withdraw, normalization and hash expiry.
- [x] Playwright sequence, each step checked after a reload: 👍 → highlighted; 👍 again → no vote; 👎 → 👎 highlighted.

## Comments

- Review (Carl): Standards 1 hard + 5 judgement (worst: spoofable X-Forwarded-For on self-host lacks a `shortcut:` comment); Spec 0 missing, 3 partial, 4 to confirm (worst: anonymized + new vote on same Song/Description both count; migrate:down deletes anonymized votes).

## Answer

Built. `POST /feedback` takes a Description, a Song ID and `up`/`down`/`none`, and stores one vote per (visitor hash, normalized Description, Song) in `feedback.votes`; `/search` returns each Match's current `vote`. The visitor hash is an HMAC-SHA256 of the IP (sent by front as `X-Visitor-IP`, read from `X-Forwarded-For`) keyed with the `IP_HASH_SALT` secret. A daily task in the API calls `feedback.forget_old_visitor_hashes()`, which nulls hashes 7 days after `created_at` and keeps the vote (migration `20261103180000_feedback_hash_expiry.sql`). Front shows labelled 👍/👎 toggle buttons on each card (optimistic, one request at a time, reverted on error) and the notice "Descrições e votos são armazenados para melhorar o modelo." under the search box.

Approved decisions: notice text; labels "Combina: {title}" / "Não combina: {title}"; hash age from `created_at`; IP from `X-Forwarded-For` (spoofable on a self-hosted `next start`, see the `shortcut:` in `front/lib/visitor.ts`); after a hash expires, a new vote on the same Song and Description adds a second row next to the anonymized one.

Tests: `back/tests/test_feedback.py` (upsert, switch, withdraw, normalization, salted hash, hash expiry), role cases in `back/tests/test_db_roles.py`, and `front/e2e/feedback.spec.ts` (👍 → 👍 again → 👎 → switch, each after a reload).
- Review (Carl, re-review): Standards 0 hard + 1 judgement (pending thumbs still show hover/active styles); Spec 0 findings, all criteria hold. Accepted pending user approval.
