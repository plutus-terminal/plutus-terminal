# Task Context: Add Context Wizard Technical Domain Update

Session ID: 2026-02-07-add-context-wizard
Created: 2026-02-07T00:00:00Z
Status: completed

## Current Request
Run the 6-question add-context wizard and update project intelligence technical patterns with strict MVI/frontmatter/navigation compliance.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/project-intelligence.md
- .opencode/context/core/context-system/standards/mvi.md
- .opencode/context/core/context-system/standards/frontmatter.md
- .opencode/context/core/context-system/standards/structure.md

## Reference Files (Source Material to Look At)
- pyproject.toml
- plutus_terminal/controller/ui_controller.py
- plutus_terminal/controller/plutus_controller.py
- plutus_terminal/core/news/news_manager.py
- plutus_terminal/core/db/models.py
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/navigation.md

## External Docs Fetched
None.

## Components
- Technical stack definition
- Component/controller pattern snapshot
- Naming conventions
- Code standards summary
- Security requirements
- Navigation alignment

## Constraints
- Keep files scannable and under 200 lines
- Use required HTML frontmatter
- Include codebase references section
- Track versions for content updates

## Exit Criteria
- [x] technical-domain.md reflects 6 wizard answers
- [x] technical-domain.md includes required frontmatter and codebase references
- [x] navigation.md updated with current metadata/routes
