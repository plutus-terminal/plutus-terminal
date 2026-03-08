<!-- Context: openagents-repo/standards/agent-frontmatter | Priority: critical | Version: 1.0 | Updated: 2026-01-31 -->
# Standard: Agent YAML Frontmatter

**Purpose**: Valid OpenCode agent frontmatter structure and common mistakes to avoid  
**Priority**: CRITICAL - Load this before creating or modifying agent files

---

## Core Principle

Agent frontmatter must contain ONLY valid OpenCode fields. All other metadata (id, name, category, tags, dependencies) belongs in `.opencode/config/agent-metadata.json`.

**Why**: OpenCode validates frontmatter strictly. Extra fields cause validation errors.

---

## Valid OpenCode Fields

### Required
```yaml
---
name: AgentName                      # Display name
description: "What this agent does"  # When to use
mode: subagent                       # primary, subagent, or all
---
```

### Optional
```yaml
temperature: 0.1                     # Response randomness (0.0-1.0)
model: anthropic/claude-sonnet-4     # Model override
maxSteps: 50                         # Max iterations
disable: false                       # Disable agent
hidden: false                        # Hide from autocomplete
prompt: "{file:./prompts/custom.txt}" # Custom prompt

tools:                               # Tool access
  read: true
  write: false
  edit: false
  bash: false
  task: false

permission:                          # Permission rules (v1.1.1+)
  "*": "ask"                         # Catch-all (last-match-wins)
  read: "allow"                      # Specific override
  bash:
    "*": "deny"
    "git status*": "allow"
  edit:
    "**/*.env*": "deny"
  task:
    contextscout: "allow"
    "*": "deny"

skills:                              # Skills to load
  - task-management
```

---

## Complete Example

```yaml
---
name: TestEngineer
description: Test authoring and TDD agent
mode: subagent
temperature: 0.1
tools:
  read: true
  grep: true
  edit: true
  write: true
  bash: true
  task: true
permission:
  bash:
    "npx vitest *": "allow"
    "pytest *": "allow"
    "sudo *": "deny"
    "*": "deny"
  edit:
    "**/*.env*": "deny"
  task:
    contextscout: "allow"
    "*": "deny"
---
```

---

## Common Mistakes (Fixed in 18 Agents)

### 1. Duplicate Keys ❌
```yaml
tools:
  read: true
  read: {"**/*": "allow"}  # ❌ Duplicate key
```
**Fix**: Use only one declaration per key

### 2. Orphaned List Items ❌
```yaml
tools:
  read: true
  - write: false  # ❌ No parent key
```
**Fix**: Proper YAML structure (no orphaned items)

### 3. Wrong Field Names ❌
```yaml
permissions:  # ❌ Deprecated - use 'permission' (singular)
  bash:
    "*": "deny"
```
**Fix**: Use correct field name `permission:` (singular, v1.1.1+)

### 4. Extra Delimiter Blocks ❌
```yaml
---
name: MyAgent
---
# Content
---  # ❌ Extra delimiter
More content
```
**Fix**: Only one `---` block at top

### 5. Invalid OpenCode Fields ❌
```yaml
---
id: my-agent          # ❌ Not valid
category: development # ❌ Not valid
type: agent           # ❌ Not valid
version: 1.0.0        # ❌ Not valid
tags: [coding]        # ❌ Not valid
dependencies: []      # ❌ Not valid
```
**Fix**: Move to `.opencode/config/agent-metadata.json`:
```json
{
  "agents": {
    "my-agent": {
      "id": "my-agent",
      "category": "development",
      "type": "agent",
      "version": "1.0.0",
      "tags": ["coding"],
      "dependencies": []
    }
  }
}
```

---

## Validation Checklist

- [ ] Only valid OpenCode fields?
- [ ] No duplicate keys?
- [ ] No orphaned list items?
- [ ] Correct field names (`permission` not `permissions`)?
- [ ] Only one `---` delimiter at top?
- [ ] Metadata moved to agent-metadata.json?
- [ ] Valid YAML syntax?

---

## Validation Commands

```bash
# Check YAML syntax
yq eval '.opencode/agent/category/agent.md' > /dev/null

# Find duplicate keys
grep -A 50 "^---$" agent.md | grep -E "^[a-z_]+:" | sort | uniq -d

# List all frontmatter keys
grep -A 50 "^---$" agent.md | grep -E "^[a-z_]+:" | cut -d: -f1
```

**Valid keys**: `name`, `description`, `mode`, `temperature`, `model`, `maxSteps`, `disable`, `hidden`, `prompt`, `tools`, `permission`, `skills`

---

## Related

- **Agent Metadata**: `core-concepts/agent-metadata.md`
- **Subagent Structure**: `standards/subagent-structure.md`
- **Adding Agents**: `guides/adding-agent.md`
- **OpenCode Docs**: https://opencode.ai/docs/agents/

---

**Last Updated**: 2026-01-31 | **Version**: 1.0.0
