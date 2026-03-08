<!-- Context: project-intelligence/business | Priority: high | Version: 1.1 | Updated: 2026-02-07 -->

# Business Domain

**Purpose**: Capture why Plutus Terminal exists, who it serves, and what value the product must protect.
**Last Updated**: 2026-02-07

## Core Concept

Plutus Terminal is an open-source desktop terminal for crypto news trading on perpetual DEX venues. It is built for traders who need fast reaction to market-moving news while keeping wallet control local. The product prioritizes speed, transparency, and user control over custody.

## Key Points

- Primary value is real-time news-to-execution workflow in one local app.
- User trust depends on local key handling, visible behavior, and explicit risk disclaimers.
- Product experience emphasizes configurable filters, notifications, and quick trade actions.
- Open-source distribution and local runtime are strategic differentiators.
- Reliability and risk controls are mandatory because actions can involve real funds.

## Project Identity

| Field | Value |
|------|------|
| Project Name | Plutus Terminal |
| Tagline | Open-source crypto news trading terminal for perpetual DEX |
| Problem Statement | Traders lose edge when news, signal filtering, and order execution are fragmented across tools. |
| Solution | A local desktop terminal that streams news, applies user filters, and enables immediate trade actions. |

## Target Users

| User Segment | Who They Are | What They Need | Pain Points |
|------|------|------|------|
| Primary | Active perpetual DEX traders | Fast news intake and rapid order entry | Missed entries, context switching, slow tooling |
| Secondary | Power users and strategy tinkerers | Custom filters, notifications, repeatable setup | Noisy feeds, inconsistent automation, low transparency |

## Value Proposition

### For Users

- React quickly to high-impact news with minimal latency in decision flow.
- Keep private keys and execution control on local infrastructure.
- Customize filtering and alerts for specific markets and sources.

### For Project

- Grow adoption through open-source trust and community contribution.
- Improve retention by combining speed, configurability, and clear risk controls.

## Success Metrics

| Metric | Definition | Target |
|------|------|------|
| News-to-action latency | Time from news display to order action availability | Minimize consistently |
| Feature reliability | Stable behavior in core flows (news, filters, trading) | High release confidence |
| User trust signals | Fewer credential/safety issues and clearer risk communication | Strict safety baseline |

## Business Constraints

- Real-money impact: product failures can cause direct financial loss.
- Compliance and safety messaging: risk/disclaimer clarity is required.
- Local-first architecture: key material handling must remain OS-secured.
- Multi-exchange evolution: feature growth must not regress core reliability.

## Quick Example

```text
News event arrives -> filter matches -> user sees quick action -> order opens on supported DEX.
If filters fail or latency spikes, user value drops immediately.
If credential handling is unsafe, trust collapses regardless of features.
```

## Reference

- Product overview and disclaimer: `README.md`
- Technical implementation patterns: `technical-domain.md`

## 📂 Codebase References

- `README.md`: project value proposition, feature list, disclaimer, and user workflow.
- `plutus_terminal/controller/ui_controller.py`: user-facing orchestration from news/events to actions.
- `plutus_terminal/core/exchange/base.py`: shared exchange contract keeping trading behavior consistent across integrations.
- `plutus_terminal/core/news/news_manager.py`: real-time news ingestion and filtering pipeline.
- `plutus_terminal/core/password_guard.py`: local credential-protection boundary.
- `plutus_terminal/core/db/models.py`: persisted local user/config/filter state.

## Related Files

- `technical-domain.md`
- `business-tech-bridge.md`
- `decisions-log.md`
