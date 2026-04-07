# Agents

## LiveKit Documentation

LiveKit is a fast-evolving project. Always refer to the latest documentation. LiveKit provides an MCP server at `https://docs.livekit.io/mcp` with tools for browsing and searching docs. Key tools: `get_docs_overview`, `get_pages`, `docs_search`, `code_search`, `get_changelog`, `get_pricing_info`. Prefer browsing (`get_docs_overview`, `get_pages`) over search, and `docs_search` over `code_search`, as docs pages provide better context than raw code.

## Best Practices

- **Begin with a starter project.** The Python and Node.js starters include working agents, tests, and an optimized AGENTS.md.
- **Read the docs like a human:** browse the table of contents first (`get_docs_overview`), search docs second (`docs_search`), and search code third (`code_search`). Browsing gives full context — search only gives fragments.
- **Always check the docs before writing LiveKit code.** The APIs change frequently and training data goes stale.
- **Use code search** to answer detailed questions about a class or method that isn't present in the docs.
- **Check the changelog** (`get_changelog`) if the docs don't match the package installed or something breaks after an upgrade.
- **Fetch full pages.** Search results only show excerpts — always fetch the full page with `get_pages` to see prerequisites and related options.
- **Practice TDD** with the agents testing framework in the Python and Node.js Agents SDKs. The testing guide also has advice on CI setup.
