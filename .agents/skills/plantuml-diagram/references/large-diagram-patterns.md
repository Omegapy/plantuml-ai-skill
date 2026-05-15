# Large Diagram Patterns

This note is distilled from the synthetic large 5,000-row validation set. The source records remain augmentation data, so use the patterns as guidance rather than copying raw examples.

## Activity

- Large activity diagrams frequently combine `if`, `switch`, `repeat`, `while`, `fork`, `split`, and swimlane markers.
- Draft a nesting outline first. Close each block with the matching terminator before opening a peer branch.
- Use `split` for independent visible work streams and `fork` for concurrent branches. Use `split again` or `fork again` for each sibling branch.
- Use short action labels and guard labels. Deep nesting with long labels renders poorly even when syntax is valid.
- Prefer explicit stop/end flow markers when a branch exits early.

## Sequence

- Large sequence diagrams frequently use multiple participants, aliases, `autonumber`, `alt`/`else`, `loop`, `opt`, `par`, `group`, activations, and dashed returns.
- Give multi-word participants stable aliases before sending messages.
- Close every combined fragment with `end`; use `else` inside `alt` fragments and between peer branches of `par` fragments.
- Use dashed arrows for responses and error returns when the user asks for outcomes.
- Keep fragment labels short and meaningful so the rendered trace stays inspectable.
