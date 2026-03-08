<!-- Context: openagents-repo/standards/navigation | Priority: critical | Version: 1.0 | Updated: 2026-01-31 -->
# OpenAgents Repo Standards

**Purpose**: Standards for creating and maintaining agents in OpenAgents Control  
**Last Updated**: 2026-01-31

---

## Overview

This directory contains standards for agent creation, focusing on:
- Valid OpenCode YAML frontmatter structure
- Subagent file organization and patterns
- Common mistakes and how to avoid them

These standards emerged from fixing YAML frontmatter issues across 18 agent files.

---

## Standards Files

| File | Description | Priority | Lines |
|------|-------------|----------|-------|
| [agent-frontmatter.md](agent-frontmatter.md) | Valid OpenCode frontmatter fields and common mistakes | critical | <200 |
| [subagent-structure.md](subagent-structure.md) | Standard structure for subagent files | critical | <200 |

---

## Quick Reference

### Valid OpenCode Fields (Frontmatter)

**Required**:
- `name` - Display name
- `description` - When to use this agent
- `mode` - Agent type (primary, subagent, all)

**Optional**:
- `temperature` - Response randomness (0.0-1.0)
- `model` - Model override
- `maxSteps` - Max iterations
- `disable` - Disable agent
- `hidden` - Hide from autocomplete
- `prompt` - Custom prompt file
- `tools` - Tool access config
- `permission` - Permission rules
- `skills` - Skills to load

### Invalid Fields (Move to agent-metadata.json)

These fields are NOT valid in OpenCode frontmatter:
- `id` - Agent identifier
- `category` - Agent category
- `type` - Component type
- `version` - Version number
- `author` - Author identifier
- `tags` - Discovery tags
- `dependencies` - Component dependencies

**Solution**: Move these to `.opencode/config/agent-metadata.json`

---

## Common Mistakes Fixed

### 1. Duplicate YAML Keys
**Problem**: `read: true` followed by `read: {"**/*": "allow"}`  
**Fix**: Use only one declaration per key

### 2. Orphaned List Items
**Problem**: Lines without parent keys (e.g., `- write: false`)  
**Fix**: Proper YAML structure with parent keys

### 3. Wrong Field Names
**Problem**: `permission:` instead of `permissions:`  
**Fix**: Use correct field name `permissions:`

### 4. Extra Delimiter Blocks
**Problem**: Multiple `---` blocks in content  
**Fix**: Only one frontmatter block at top

### 5. Invalid OpenCode Fields
**Problem**: Fields like `id`, `category`, `type` in frontmatter  
**Fix**: Move to agent-metadata.json

---

## Loading Strategy

### For Creating New Agents
1. Load `agent-frontmatter.md` - Understand valid fields
2. Load `subagent-structure.md` - Follow structure pattern
3. Reference existing agents as examples
4. Validate YAML syntax before committing

### For Fixing Existing Agents
1. Load `agent-frontmatter.md` - Identify invalid fields
2. Check for common mistakes (duplicates, orphans, wrong names)
3. Move invalid fields to agent-metadata.json
4. Validate with YAML parser

### For Code Reviews
1. Load `agent-frontmatter.md` - Check frontmatter validity
2. Load `subagent-structure.md` - Verify structure compliance
3. Check for common mistakes
4. Validate YAML syntax

---

## Validation Commands

### Check YAML Syntax
```bash
yq eval '.opencode/agent/category/agent.md' > /dev/null
```

### Check for Duplicate Keys
```bash
grep -A 50 "^---$" .opencode/agent/category/agent.md | grep -E "^[a-z_]+:" | sort | uniq -d
```

### List All Frontmatter Keys
```bash
grep -A 50 "^---$" .opencode/agent/category/agent.md | grep -E "^[a-z_]+:" | cut -d: -f1
```

Valid keys: `name`, `description`, `mode`, `temperature`, `model`, `maxSteps`, `disable`, `hidden`, `prompt`, `tools`, `permissions`, `skills`

---

## Related Context

### Core Concepts
- [Agent Metadata System](../core-concepts/agent-metadata.md) - Centralized metadata management
- [Agents](../core-concepts/AGENTS.md) - Agent system overview
- [Categories](../core-concepts/categories.md) - Agent categorization

### Guides
- [Adding Agents](../guides/adding-agent.md) - How to create new agents
- [Testing Agents](../guides/testing-agent.md) - Agent testing workflow

### Lookup
- [File Locations](../lookup/file-locations.md) - Where files go

---

## History

**2026-01-31**: Initial standards created after fixing YAML frontmatter issues in 18 agent files. Issues fixed:
- Duplicate YAML keys (e.g., `read: true` + `read: {"**/*": "allow"}`)
- Orphaned list items (lines without parent keys)
- Wrong field names (`permission:` → `permissions:`)
- Extra `---` delimiter blocks in content
- Invalid OpenCode fields in frontmatter

---

**Version**: 1.0.0  
**Maintainer**: OpenAgents Control Team
