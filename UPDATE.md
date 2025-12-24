# Updating Skills

Since you've cloned this repository, you can easily get the latest versions of skills.

## Update All Skills

```bash
cd ~/.claude/claude-common-skills
git pull
```

That's it! All symlinked skills will automatically use the updated versions.

## Adding New Skills

When new skills are added to this repository:

1. Pull the latest changes:
   ```bash
   cd ~/.claude/claude-common-skills
   git pull
   ```

2. Create a symlink for the new skill:
   ```bash
   ln -sf ~/.claude/claude-common-skills/skills/NEW-SKILL-NAME ~/.claude/skills/NEW-SKILL-NAME
   ```

## Verifying Installation

Check your installed skills:

```bash
ls -la ~/.claude/skills/
```

You should see symlinks pointing to `~/.claude/claude-common-skills/skills/...`

## Troubleshooting

**Skills not working?**
- Ensure symlinks are correct: `ls -la ~/.claude/skills/`
- Verify repository is up to date: `cd ~/.claude/claude-common-skills && git status`
- Try restarting Claude Code

**Broken symlinks?**
If you moved the repository, recreate symlinks:
```bash
# Remove old symlinks
rm ~/.claude/skills/portainer-deploy

# Create new ones
ln -sf ~/.claude/claude-common-skills/skills/portainer-deploy ~/.claude/skills/portainer-deploy
```
