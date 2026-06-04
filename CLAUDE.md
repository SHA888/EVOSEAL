# CLAUDE.md

Project conventions for Claude Code (and any AI assistant) working in this repository.

## Commit messages

- **Do not include `Co-Authored-By:` trailers in commit messages.** This applies to
  all assistant-generated commits, including those produced by Claude Code or any
  other AI tool. Commit attribution stays with the human author. Boilerplate trailers
  add noise to the history without conveying meaningful authorship and have been
  retroactively stripped from past commits.

## English-only requirement

- All `Plans.md` content must be in English (headers, table columns, task
  descriptions, status markers).
- No Japanese characters in `Plans.md` status markers (use `cc:done` instead of
  `cc:完了`, `cc:wip` instead of `cc:WIP`, etc).
- All harness output and documentation must be in English.
- This applies strictly to tracked files; commit to this constraint when editing
  `Plans.md`.
