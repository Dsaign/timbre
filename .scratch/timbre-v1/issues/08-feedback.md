# 08: Feedback

**What to build:** the visitor can vote 👍 or 👎 on each Match, switch the vote, or press the same thumb again to withdraw it. The vote survives a reload. A short notice explains that Descriptions and votes are stored to improve the model. Nothing stored identifies the visitor.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The `feedback` schema stores votes with: normalized Description, Song ID, vote, timestamps and a salted visitor hash. The IP-hash salt is a secret.
- [ ] A Feedback endpoint takes a Description, a Song ID and a vote: up, down, or none (withdraw). There is one vote per (visitor hash, normalized Description, Song), and the latest wins.
- [ ] Descriptions are normalized as: Unicode NFC, trimmed, whitespace collapsed, lowercased.
- [ ] Search responses include the visitor's current vote for each Match.
- [ ] A daily timer in the API process clears visitor hashes older than 7 days (the hash becomes null) and keeps the vote.
- [ ] Front: 👍/👎 on each card, with the current vote highlighted. Pressing the other thumb switches the vote, and pressing the same thumb withdraws it. Updates are optimistic and reverted on error. Both buttons are labelled and keyboard-reachable.
- [ ] A privacy notice under the search box says that Descriptions and votes are stored to improve the model.
- [ ] API tests cover upsert, switch, withdraw, normalization and hash expiry.
- [ ] Playwright sequence, each step checked after a reload: 👍 → highlighted; 👍 again → no vote; 👎 → 👎 highlighted.
