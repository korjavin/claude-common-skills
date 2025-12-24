---
name: portainer-deploy
description: Setup automated deployment with GitHub Actions, ghcr.io, and Portainer webhooks. Supports Traefik reverse proxy and multi-service Docker Compose. Use when user wants to setup CI/CD, deployment, or Portainer integration.
---

# Portainer Deploy Skill

This skill helps set up automated deployment pipeline with:
- GitHub Container Registry (ghcr.io)
- GitHub Actions for CI/CD
- Portainer webhooks for automatic redeployment
- Traefik reverse proxy support
- Multi-service Docker Compose support

## When to Use This Skill

Use this skill when the user wants to:
- Set up automated deployment for their project
- Configure CI/CD with GitHub Actions
- Integrate with Portainer for container management
- Add Traefik reverse proxy with automatic HTTPS
- Deploy multi-service applications

## Deployment Process

### 1. Analyze Project Structure

First, understand the current project setup:

```bash
# Check for existing files
ls -la Dockerfile docker-compose.yml .github/workflows/
```

Determine:
- Is there a Dockerfile? (if not, this skill cannot help - Dockerfile is required)
- Is there a docker-compose.yml? (analyze or create)
- Are there existing GitHub Actions workflows?
- How many services does the project need? (single or multi-service)
- What is the main branch name? (main or master)

### 2. Interactive Questions

If uncertain, ask the user:

1. **Main branch**: "What is your main branch name? (main/master)"
2. **Services**: "Is this a single service or multi-service application?"
3. **Traefik**: "Do you want to use Traefik reverse proxy with automatic HTTPS? (yes/no)"
4. **Domain**: If Traefik - "What domain will you use? (e.g., example.com)"
5. **Network**: If Traefik - "What is your Traefik network name? (default: traefik_network)"
6. **Webhooks**: "How many Portainer stacks will you deploy? (usually 1, or 2+ for multi-stack)"

### 3. Generate or Update GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

**Key elements:**
- Trigger on push to main branch + workflow_dispatch
- Login to ghcr.io using GITHUB_TOKEN
- Build and push Docker image with tags: `latest` and `${{ github.sha }}`
- Update docker-compose.yml with new image tag using sed
- Commit changes to `deploy` branch
- Trigger Portainer webhook(s)

**Template reference:** See `templates/github-workflow.yml`

**Important notes:**
- Use `ghcr.io/${{ github.repository_owner }}/${{ github.event.repository.name }}` for image name
- Update ALL docker-compose files if multiple exist (e.g., main + bot-hoster)
- Add multiple webhook steps if deploying to multiple Portainer stacks

### 4. Generate or Update docker-compose.yml

**For single service with Traefik:**
```yaml
version: "3.8"

services:
  app:
    image: ghcr.io/OWNER/REPO:latest
    container_name: app-name
    networks:
      - traefik_network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app.rule=Host(`${HOSTNAME}`)"
      - "traefik.http.routers.app.entrypoints=websecure"
      - "traefik.http.routers.app.tls.certresolver=myresolver"
      - "traefik.http.services.app.loadbalancer.server.port=8080"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - ENV_VAR=${ENV_VAR}

networks:
  traefik_network:
    external: true
```

**For multi-service:**
- Include all services (e.g., app + database + cache)
- Set up service dependencies with `depends_on`
- Use same image for multiple services with different `command` if needed
- Configure internal networks for inter-service communication

**Template reference:** See `templates/docker-compose-traefik.yml` and `templates/docker-compose-simple.yml`

### 5. Update Strategy

**If files exist:**

1. **GitHub Actions workflow exists:**
   - Check if it's similar to our pattern (build → push → update compose → webhook)
   - If similar: Update in place (fix image tags, add missing webhooks, etc.)
   - If different: Ask user if they want to replace or keep existing

2. **docker-compose.yml exists:**
   - Check if it has correct image format (ghcr.io/owner/repo:latest)
   - Check if Traefik labels are present (if user wants Traefik)
   - Update image tags to use ghcr.io format
   - Add Traefik labels if requested
   - Preserve existing environment variables and volumes

**If files don't exist:**
- Create new files from templates
- Customize based on project structure

### 6. Remind About Secrets

After generating files, remind the user:

```
Important: Add the following secret to your GitHub repository:

1. Go to: https://github.com/OWNER/REPO/settings/secrets/actions
2. Click "New repository secret"
3. Name: PORTAINER_REDEPLOY_HOOK
4. Value: Your Portainer webhook URL (get from Portainer stack settings)

If you have multiple stacks, add:
- PORTAINER_REDEPLOY_HOOK_2 (for second stack)
- PORTAINER_REDEPLOY_HOOK_BOT (for bot-hoster, etc.)

To get webhook URL from Portainer:
1. Open your stack in Portainer
2. Click on "Webhooks"
3. Copy the webhook URL
```

## Project Examples

Refer to these projects for patterns:

1. **virusgame** - Multi-service with WebSocket support
2. **madrookbot** - Multi-service (bot + qdrant + tool-api)
3. **countrycounter** - Single service with Traefik

## Troubleshooting

**Image tags not updating:**
- Check sed patterns in GitHub Actions workflow
- Verify all docker-compose files are included in sed commands

**Webhook not triggering:**
- Verify secret name matches in workflow and GitHub settings
- Check Portainer webhook URL is correct
- Test webhook manually with curl

**Traefik not routing:**
- Verify network exists: `docker network ls`
- Check Traefik labels syntax
- Ensure HOSTNAME environment variable is set

## Implementation Checklist

After running this skill, verify:

- [ ] `.github/workflows/deploy.yml` created/updated
- [ ] `docker-compose.yml` has correct image format
- [ ] Traefik labels added (if requested)
- [ ] User reminded about GitHub secrets
- [ ] All services defined in compose file
- [ ] Environment variables documented
- [ ] Volumes configured for persistence

## Next Steps for User

After setup:

1. Add PORTAINER_REDEPLOY_HOOK to GitHub secrets
2. Set up Portainer stack using the docker-compose.yml
3. Configure environment variables in Portainer
4. Test deployment: Push to main branch
5. Verify Portainer auto-updates the stack
