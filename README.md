# Claude Common Skills

A collection of reusable skills for [Claude Code](https://claude.com/claude-code) to automate common development tasks.

## What are Claude Skills?

Claude Skills are modular extensions that enhance Claude Code's capabilities. They provide specialized knowledge and workflows for specific tasks, making Claude more effective at handling complex scenarios.

## Available Skills

### Agent process (bd / beads delivery)

| Skill | What it does |
|---|---|
| [orchestrate](./skills/orchestrate/) | Supervises developer agents to deliver bd work end-to-end at a chosen concurrency; verifies and merges PRs |
| [architect](./skills/architect/) | Planner: clarifies requirements, root-causes bugs, files bd issues/epics; never writes code |
| [develop](./skills/develop/) | Delivers one bd issue: implement, review, PR, CI green, hand off for merge |
| [curator](./skills/curator/) | Audits past agent sessions for waste and mistakes, turns findings into skill/CLAUDE.md improvements |
| [open-pr-review](./skills/open-pr-review/) | Triages open PRs (e.g. from coding agents): merge, comment or close |
| [handoff](./skills/handoff/) | Writes a HANDOFF.md so a fresh agent can continue the task |

### agterm terminal

| Skill | What it does |
|---|---|
| [agterm](./skills/agterm/) | Drives the agterm macOS terminal via `agtermctl`: sessions, panes, overlays, HTML pages, pickers, events |
| [agterm-ask](./skills/agterm-ask/) | Asks the owner questions as an HTML page with buttons, returns answers as JSON |
| [peer-chat](./skills/peer-chat/) | Back-and-forth conversation with a Codex/AGY agent in another agterm pane |
| [claude-recap](./skills/claude-recap/) | Recaps what a Claude session in an agterm session was working on |

### Messaging and other agents

| Skill | What it does |
|---|---|
| [zulip-post](./skills/zulip-post/) | Posts to Zulip as a bot, waiting for image thumbnails so they don't render as spinners |
| [zulip-wait](./skills/zulip-wait/) | Waits for a Zulip reply without polling, via [zulip_watcher](https://github.com/korjavin/zulip_watcher) |
| [omniagent-telegram-alert](./skills/omniagent-telegram-alert/) | Telegram alert when an agent is blocked and needs the owner |
| [hermes](./skills/hermes/) | Delegates a task to the owner's Hermes agent over A2A |
| [devbox](./skills/devbox/) | Delegates a task to Claude Code on the owner's devbox over A2A |
| [stash](./skills/stash/) | Reads/writes secrets and config in a local [stash](https://github.com/umputun/stash) store via `kv` |

### Deployment and infrastructure

| Skill | What it does |
|---|---|
| [portainer-deploy](./skills/portainer-deploy/) | GitHub Actions + ghcr.io + Portainer webhooks, Traefik, multi-service compose |
| [compose-service-setup](./skills/compose-service-setup/) | Git-ops compose project for a 3rd-party service, optional GHCR image vendoring |
| [litestream-backup](./skills/litestream-backup/) | SQLite replication to S3/R2/MinIO with Litestream |
| [prod-debug](./skills/prod-debug/) | Debugs production over SSH: logs, env, behavior |
| [setup-dev-host](./skills/setup-dev-host/) | Bootstraps a new dev host: core tools, dotfiles, these skills |

### Web and app development

| Skill | What it does |
|---|---|
| [create-go-web-project](./skills/create-go-web-project/) | Scaffolds a Go web project from your preferences |
| [telegram-web-login](./skills/telegram-web-login/) | Adds Telegram Login Widget auth to a web app |
| [mcp-registry-executor](./skills/mcp-registry-executor/) | MCP server design: discovery tool + sandboxed code executor over an operation registry |
| [ada-compliance](./skills/ada-compliance/) | WCAG 2.2 AA audit and fix with axe-core in real Chromium |
| [agent-browser](./skills/agent-browser/) | Browser automation CLI for agents: navigate, fill forms, screenshot, scrape |

### Notes and publishing

| Skill | What it does |
|---|---|
| [outline-sort-inbox](./skills/outline-sort-inbox/) | Sorts the Outline "Inbox": summarize, tag, file into "SortedInbox" |
| [outline-dream](./skills/outline-dream/) | Restructures "SortedInbox": merges duplicates, splits/flattens folders |
| [thingiverse-publish](./skills/thingiverse-publish/) | Publishes a 3D model from the repo to Thingiverse and links it in the README |

## Installation

### Option 1: Personal Skills with Auto-Updates (Recommended)

Clone the repository and use symlinks for automatic updates:

```bash
# Clone to your Claude directory
cd ~/.claude
git clone https://github.com/korjavin/claude-common-skills.git

# Create symlinks (stays updated when you git pull)
mkdir -p ~/.claude/skills
for d in ~/.claude/claude-common-skills/skills/*/; do ln -sfn "$d" ~/.claude/skills/"$(basename "$d")"; done

# To update later, just run:
# cd ~/.claude/claude-common-skills && git pull
```

### Option 2: Personal Skills (Copy Once)

Copy skills to your personal Claude directory:

```bash
# Clone this repository
git clone https://github.com/korjavin/claude-common-skills.git

# Copy skills to personal directory
cp -r claude-common-skills/skills/* ~/.claude/skills/
```

### Option 3: Project Skills (Shared with Team)

Add skills to your project:

```bash
# In your project directory
git clone https://github.com/korjavin/claude-common-skills.git /tmp/claude-skills
cp -r /tmp/claude-skills/skills/* .claude/skills/

# Commit to share with team
git add .claude/skills/
git commit -m "Add Claude skills"
git push
```

## Usage

Once installed, skills activate automatically when you ask Claude relevant questions:

```
"Set up deployment with Portainer"
"/orchestrate 2"
"Post the release note to zulip"
```

Claude will use the appropriate skill and guide you through the process.

## Skill Structure

Each skill follows this structure:

```
skills/
└── skill-name/
    ├── SKILL.md          # Main instructions for Claude (required)
    ├── README.md         # Documentation for users (optional)
    ├── examples.md       # Examples (optional)
    ├── reference.md      # Detailed reference (optional)
    └── scripts/          # Helper scripts (optional)
```

## Contributing

Have a useful skill to share? Contributions are welcome!

1. Fork this repository
2. Create your skill in `skills/your-skill-name/`
3. Follow the [skill structure](#skill-structure)
4. Submit a pull request

## Requirements

- [Claude Code](https://claude.com/claude-code) installed
- Skills are compatible with Claude Code CLI

## License

MIT License - feel free to use and modify these skills for your projects.

## Related Resources

- [Claude Code Documentation](https://code.claude.com/docs)
- [Agent Skills Guide](https://code.claude.com/docs/en/skills.md)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)

## Feedback

Found a bug or have a suggestion? [Open an issue](https://github.com/korjavin/claude-common-skills/issues)!
