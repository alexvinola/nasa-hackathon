---
name: explore-codebase
description: Explore an unfamiliar large codebase using an optional Graphify map alongside direct source searches. Use when understanding dependencies or locating cross-module flows is difficult.
---

# Explore a codebase

Start with project instructions, entry points and direct searches (`rg`, symbol
navigation). If `graphify-out/GRAPH_REPORT.md` exists, use it as an additional map:
check whether it reflects the current checkout and read the source to confirm
its claims. Do not restrict investigation to the files the graph suggests.

When Graphify is installed, useful queries are:

```bash
graphify query "what connects billing to orders?"
graphify path "BillingService" "OrderRepository"
graphify explain "BillingService"
```

After structural changes, refresh an actively maintained map with
`graphify . --update` when that is part of the project's workflow. A stale or
unavailable graph must not block source exploration.

If a large project would benefit and has no map, suggest setup without installing
it unasked: `uv tool install graphifyy`, `graphify install`, then `/graphify .` in
the project. The developer controls tools and any model credentials they need.

Reference: https://graphify.com/llms-full.txt
