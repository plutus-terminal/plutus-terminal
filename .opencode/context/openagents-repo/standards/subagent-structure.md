<!-- Context: openagents-repo/standards/subagent-structure | Priority: critical | Version: 1.0 | Updated: 2026-01-31 -->
# Standard: Subagent File Structure

**Purpose**: Standard structure for subagent files  
**Priority**: CRITICAL - Load this before creating subagent files

---

## File Template

```markdown
---
name: AgentName
description: Brief description
mode: subagent
temperature: 0.1
tools: {...}
permissions: {...}
---

# AgentName
> **Mission**: One-sentence mission

<rule id="rule_name">Rule description</rule>

<context>
  <system>Role in pipeline</system>
  <domain>Expertise area</domain>
  <task>What agent does</task>
  <constraints>Limitations</constraints>
</context>

<tier level="1" desc="Critical">
  - @rule_id: Description
</tier>

## Workflow
### Step 1: Preparation
### Step 2: Execution
### Step 3: Output

## Output Format
```yaml
status: "success" | "failure"
```
```

---

## Section Details

### 1. Frontmatter
- ONLY valid OpenCode fields (see agent-frontmatter.md)
- No duplicate keys, orphaned items, or invalid fields

### 2. Header + Mission
```markdown
# TestEngineer
> **Mission**: Author tests following TDD — grounded in project standards.
```

### 3. Critical Rules (3-5 max)
```markdown
<rule id="context_first">ALWAYS call ContextScout BEFORE writing tests.</rule>
<rule id="positive_and_negative">EVERY behavior needs positive AND negative tests.</rule>
```

### 4. Context
```markdown
<context>
  <system>Code quality gate</system>
  <domain>Code review, security, quality</domain>
  <task>Review code against standards</task>
  <constraints>Read-only, no modifications</constraints>
</context>
```

### 5. Execution Tiers
```markdown
<tier level="1" desc="Critical">
  - @context_first: Load context first
</tier>
<tier level="2" desc="Core">
  - Load standards
  - Analyze code
</tier>
<conflict_resolution>Tier 1 overrides Tier 2/3</conflict_resolution>
```

---

## Tool Permission Patterns

### Read-Only (Reviewers, Analyzers)
```yaml
tools: {read: true, grep: true, glob: true, bash: false, edit: false, write: false}
permissions:
  bash: {"*": "deny"}
  edit: {"**/*": "deny"}
  task: {contextscout: "allow", "*": "deny"}
```

### Write-Enabled (Coders, Testers)
```yaml
tools: {read: true, edit: true, write: true, bash: true}
permissions:
  bash: {"npm test *": "allow", "git *": "allow", "sudo *": "deny", "*": "deny"}
  edit: {"**/*.env*": "deny", "**/*.key": "deny"}
  task: {contextscout: "allow", "*": "deny"}
```

### Restricted Bash (Task Managers)
```yaml
tools: {read: true, bash: true}
permissions:
  bash: {"npx ts-node*task-cli*": "allow", "mkdir -p .tmp/tasks*": "allow", "*": "deny"}
```

---

## File Organization

```
.opencode/agent/subagents/
├── code/           # tester, reviewer, coder-agent, build-agent
├── core/           # task-manager, contextscout, documentation
├── system-builder/ # agent-generator, command-creator
└── utils/          # image-specialist
```

---

## Validation Checklist

- [ ] Valid OpenCode frontmatter (no extra fields)?
- [ ] Mission statement present?
- [ ] 3-5 critical rules with unique IDs?
- [ ] Context section complete?
- [ ] Execution tiers defined with conflict resolution?
- [ ] Workflow steps clear and actionable?
- [ ] Output format specified?
- [ ] Tool permissions appropriate for role?
- [ ] File in correct category directory?
- [ ] No YAML syntax errors?

---

## Common Patterns

**Context-First Pattern**:
```markdown
<rule id="context_first">
  ALWAYS call ContextScout BEFORE starting work. Load relevant standards first.
</rule>
```

**Read-Only Pattern**:
```markdown
<rule id="read_only">
  Read-only agent. NEVER use write, edit, or bash. Provide suggestions only.
</rule>
```

**Security Pattern**:
```markdown
permissions:
  edit:
    "**/*.env*": "deny"
    "**/*.key": "deny"
    "**/*.secret": "deny"
```

---

## Examples

**See existing subagents**:
- `.opencode/agent/subagents/code/tester.md` - Write-enabled with tests
- `.opencode/agent/subagents/code/reviewer.md` - Read-only reviewer
- `.opencode/agent/subagents/core/task-manager.md` - Restricted bash

---

## Related

- **Frontmatter**: `standards/agent-frontmatter.md`
- **Metadata**: `core-concepts/agent-metadata.md`
- **Adding Agents**: `guides/adding-agent.md`

---

**Last Updated**: 2026-01-31 | **Version**: 1.0.0
