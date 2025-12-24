# Claude Common Skills

A collection of reusable skills for [Claude Code](https://claude.com/claude-code) to automate common development tasks.

## What are Claude Skills?

Claude Skills are modular extensions that enhance Claude Code's capabilities. They provide specialized knowledge and workflows for specific tasks, making Claude more effective at handling complex scenarios.

## Available Skills

### 🚀 [portainer-deploy](./skills/portainer-deploy/)

Automates deployment setup with GitHub Actions, GitHub Container Registry (ghcr.io), and Portainer webhooks.

**Features:**
- GitHub Actions workflow generation
- Docker Compose with Traefik support
- Multi-service deployments
- Automatic image tagging with commit SHA
- Portainer webhook integration

**Use when:**
- Setting up CI/CD for Docker projects
- Deploying with Portainer
- Configuring Traefik reverse proxy
- Managing multi-service applications

[📖 Read more](./skills/portainer-deploy/README.md)

## Installation

### Option 1: Personal Skills with Auto-Updates (Recommended)

Clone the repository and use symlinks for automatic updates:

```bash
# Clone to your Claude directory
cd ~/.claude
git clone https://github.com/korjavin/claude-common-skills.git

# Create symlinks (stays updated when you git pull)
mkdir -p ~/.claude/skills
ln -sf ~/.claude/claude-common-skills/skills/portainer-deploy ~/.claude/skills/portainer-deploy

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
"Configure CI/CD for this project"
"Add Traefik reverse proxy"
```

Claude will use the appropriate skill and guide you through the process.

## Skill Structure

Each skill follows this structure:

```
skills/
└── skill-name/
    ├── SKILL.md          # Main instructions for Claude (required)
    ├── README.md         # Documentation for users
    ├── examples.md       # Real-world examples
    ├── reference.md      # Detailed reference
    └── templates/        # Template files
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
