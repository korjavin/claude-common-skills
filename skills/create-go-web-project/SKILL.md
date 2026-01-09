# Create Go Web Project Skill

You are a project scaffolding assistant that creates new Go web projects based on user preferences.

## Workflow

1. **Gather Project Requirements** - Ask the user the following questions one at a time:

   1. **GitHub username/org**: Your GitHub username or organization (e.g., "john" or "mycompany")

   2. **Project name**: GitHub repository name (e.g., "my-awesome-app")
      - Full module path will be: `github.com/{username}/{project-name}`

   3. **Project type** (describe options clearly):
      - **Pure Go API** - REST API, no frontend, just backend endpoints
      - **Go + Vanilla HTML/JS** - Simple frontend served as static files, no build step
      - **Go + React (Vite)** - Full SPA with TypeScript, Vite build pipeline, React Router
      - **Go + Telegram Bot** - Telegram bot only, optional simple web dashboard
      - **Go + Telegram Bot + Web** - Telegram bot with full web UI

   3. **Google OAuth2 authentication?** (y/n) - Adds Google login via golang.org/x/oauth2

   4. **Include Telegram integration?** (y/n) - Adds Telegram bot support via `github.com/go-telegram-bot-api/telegram-bot-api`

      If yes, ask: **Include Telegram WebApp Auth for web login?** (y/n) - Allows users to authenticate on web via Telegram WebApp initData

   5. **SQLite database with sqlc?** (y/n) - Type-safe SQL access layer with migrations

   6. **Litestream backup to R2/S3?** (y/n) - Only ask if SQLite was selected. Adds continuous DB backup to object storage with separate credentials. Includes auto-restore on startup.

   7. **R2/S3 object storage?** (y/n) - File uploads to Cloudflare R2 or AWS S3

   8. **WebSocket support?** (y/n) - Adds gorilla/websockets or equivalent for real-time features

   9. **Rate limiting middleware?** (y/n) - Adds basic IP-based rate limiting

   10. **CORS middleware?** (y/n) - Adds configurable CORS headers for cross-origin requests

   11. **Email notifications?** (y/n) - Adds email sending capability (configure via SMTP or service like SendGrid/Mailgun)

   12. **Use Go vendoring?** (y/n) - Vendor dependencies for reproducible builds (`go mod vendor`, build with `-mod vendor`)

   13. **Create GitHub repository?** (y/n) - Uses `gh` CLI to create repo
       - If yes, ask: **Public or private?** (default: public)
       - **License?** (default: MIT) - Options: MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, or none
       - **Short description?** - One-line project description for GitHub

2. **Create Project Structure** based on selections:

   ```
   {project-name}/
   ├── cmd/
   │   └── server/main.go
   ├── internal/
   │   ├── api/           # HTTP handlers
   │   ├── auth/          # OAuth + session handling
   │   ├── db/            # Database connection
   │   ├── middleware/    # CORS, rate limiting, logging
   │   ├── repository/    # sqlc generated layer
   │   ├── service/       # Business logic
   │   └── storage/       # R2/S3 client
   ├── sql/
   │   ├── migrations/
   │   └── queries/       # sqlc query files
   ├── web/               # or frontend/ for React
   │   ├── index.html
   │   ├── css/
   │   └── js/
   ├── .github/workflows/
   │   ├── deploy.yml
   │   └── dev-deploy.yml
   ├── Dockerfile
   ├── .dockerignore
   ├── docker-compose.yml
   ├── .env.example
   ├── .gitignore
   ├── README.md
   ├── agents.md
   ├── go.mod
   ├── start.sh
   └── sqlc.yaml
   ```

3. **Generate Files** based on project type and features:

   ### Always Generate:
   - `.gitignore` (standard Go + Node patterns)
   - `.dockerignore` (exclude .git, .env, node_modules, test files, docs)
   - `.env.example` with all relevant variables
   - `README.md` with setup instructions, environment variables, deployment guide
   - `agents.md` explaining project structure for AI assistants
   - `go.mod` with appropriate dependencies
   - `start.sh` for local development
   - Healthcheck endpoint at `/health` returning `{"status": "ok"}`
   - Graceful shutdown handling (SIGINT/SIGTERM with 30s timeout)
   - Structured logging with `log/slog`

   ### Based on Project Type:

   **Pure Go API**:
   - Minimal HTTP handlers in `internal/api/`
   - No static file serving

   **Go + Vanilla HTML/JS**:
   - `web/index.html` with vanilla JS/CSS
   - Go serves static files from `web/`

   **Go + React (Vite)**:
   - `frontend/` with full Vite + React + TypeScript setup
   - `frontend/package.json`, `vite.config.ts`, `tsconfig.json`
   - Go serves built frontend from `frontend/dist/`

   **Go + Telegram Bot**:
   - `cmd/bot/main.go` entry point
   - Uses `github.com/go-telegram-bot-api/telegram-bot-api`
   - Simple web handler for health checks

   **Go + Telegram Bot + Web**:
   - Both bot and web handlers
   - Shared services between bot and web

   ### Based on Features:

   **Google OAuth2**:
   - `internal/auth/google.go` with OAuth2 config, session management, admin whitelist
   - Protected routes middleware
   - Environment: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URL`, `ADMIN_EMAILS`, `COOKIE_SECRET`

   **Telegram WebApp Auth**:
   - `internal/auth/telegram.go` with initData HMAC-SHA256 validation
   - Auth middleware that validates `X-Telegram-Init-Data` header
   - Environment: `TG_BOT_TOKEN`

   **SQLite + sqlc**:
   - `sqlc.yaml` configuration pointing to migrations for schema
   - Migrations using `github.com/pressly/goose/v3`:
     - SQL files in designated folder (e.g., `internal/store/migrations/`)
     - Embedded using `//go:embed migrations/*.sql`
     - Naming: `001_init.sql`, `002_add_users.sql`, etc.
   - `sql/queries/` with sqlc query definitions
   - `internal/repository/` sqlc-generated code
   - Database connection with WAL mode enabled
   - Migrations auto-run on startup via `goose.Up(db, "migrations")`
   - Environment: `DB_PATH`

   **Litestream** (only when SQLite selected):
   - `docker-compose.yml` with litestream service
   - Auto-restore on container startup (restore from R2 before app starts)
   - Separate R2 credentials: `LITESTREAM_R2_ACCESS_KEY_ID`, `LITESTREAM_R2_SECRET_ACCESS_KEY`, `LITESTREAM_R2_ACCOUNT_ID`, `LITESTREAM_R2_BUCKET_NAME`

   **R2/S3 Storage**:
   - `internal/storage/r2.go` using AWS SDK v2
   - Environment: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_PUBLIC_DOMAIN`

   **WebSocket**:
   - `internal/api/ws.go` with upgrade handler
   - Example connection in web frontend

   **Rate Limiting**:
   - `internal/middleware/ratelimit.go`
   - Applied to relevant routes

   **CORS**:
   - `internal/middleware/cors.go` with configurable origins
   - Environment: `CORS_ORIGINS` (comma-separated list, default: `*`)

   **Email**:
   - `internal/service/email.go` with SendGrid/Mailgun support
   - Environment: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`

   **Vendoring**:
   - Run `go mod vendor` after generating `go.mod`
   - **IMPORTANT**: Remove `vendor/` from `.gitignore` so it gets committed
   - Vendor directory MUST be committed to repo for Docker builds to work
   - Update Dockerfile to copy vendor directory and use `-mod vendor` flag

4. **Docker & CI/CD**:

   **Dockerfile** (multi-stage):
   ```dockerfile
   # Build stage
   FROM golang:1.24-alpine AS builder
   WORKDIR /app

   # Copy go mod files first for better caching
   COPY go.mod go.sum ./

   # Copy vendor directory (if using vendoring)
   COPY vendor/ ./vendor/

   # Copy the rest of the application
   COPY . .

   # Build using vendor directory (no go mod download needed)
   RUN CGO_ENABLED=0 GOOS=linux go build -mod vendor -o server ./cmd/server

   # Build the bot (if using bot)
   RUN CGO_ENABLED=0 GOOS=linux go build -mod vendor -o bot ./cmd/bot

   # Runtime stage
   FROM alpine:latest
   RUN apk --no-cache add ca-certificates
   WORKDIR /app
   COPY --from=builder /app/server .
   COPY --from=builder /app/bot .
   # Copy frontend if exists
   COPY web/ ./web/  # or frontend/dist/ for React
   COPY sql/migrations/ ./sql/migrations/
   EXPOSE 8080
   CMD ["./server"]
   ```

   **docker-compose.yml**:
   - Main service with environment from `.env`
   - Traefik labels for routing (if applicable)
   - Volume for SQLite data
   - Litestream service with auto-restore (if selected)

   **deploy.yml** (GitHub Actions):
   - Build and push to GHCR on master push
   - Update `deploy` branch with new image tag in docker-compose.yml
   - Trigger Portainer webhook via `PORTAINER_WEBHOOK` secret

   **dev-deploy.yml** (GitHub Actions):
   - Build on any branch except master
   - Tag with branch name
   - Update `deploy-dev` branch
   - Trigger Portainer webhook via `PORTAINER_WEBHOOK_DEV` secret

5. **Testing**:
   - Create `*_test.go` files with standard `testing` package
   - Use table-driven tests
   - Example tests in `internal/service/` and `internal/api/`

6. **Initialize Git & GitHub**:
   - `git init`
   - Create initial commit with message "Initial commit: project scaffolding"
   - If GitHub repo creation was selected:
     ```bash
     gh repo create {project-name} --public/--private --description "{description}"
     ```
   - Add remote and push:
     ```bash
     git remote add origin https://github.com/{username}/{project-name}.git
     git push -u origin master
     ```
   - After initial push, create LICENSE file separately if license was requested (gh CLI doesn't support `--license` flag)

## Output

After gathering all preferences and generating files:
- Show the created directory structure
- List generated files
- Provide next steps (push to GitHub, configure secrets, deploy)
- Remind user to copy `.env.example` to `.env` and fill in values

## Important Notes

- **Use pure Go SQLite**: Use `modernc.org/sqlite` (pure Go, no CGO) instead of `github.com/mattn/go-sqlite3`. This simplifies builds and allows `CGO_ENABLED=0`.
- Use separate R2 credentials for Litestream (don't reuse main app credentials)
- All secrets should be referenced from environment variables
- Keep dependencies minimal - prefer standard library where possible
- Use sqlc for SQLite (generates type-safe Go from SQL)
- Google OAuth2 + Telegram WebApp Auth are independent choices
- Rate limiting and CORS should be middleware that can be applied selectively
- README should include: quick start, environment variables, deployment steps
- agents.md should explain: where things are, how to add new endpoints, common patterns
- Always include healthcheck endpoint and graceful shutdown
- Use `log/slog` for structured logging (standard library, no external deps)
- If vendoring selected, use `-mod vendor` flag in build commands

## Troubleshooting & Lessons Learned

### Telegram Bot Package Issues
**Problem**: `github.com/telegram-bot-api/v5` package may not exist or be unavailable.

**Solution**: Use `github.com/go-telegram-bot-api/telegram-bot-api` instead (v4.6.4+incompatible).

```go
// Import like this:
import tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api"
```

### Module Import Path Mismatch
**Problem**: Go modules use the GitHub repository path (e.g., `github.com/username/projectname`), but when creating files locally before pushing, Claude may use a local path like `github.com/iv/Projects/testapp`.

**Solution**:
1. First ask user for their GitHub username/org BEFORE generating code
2. Use `github.com/{username}/{project-name}` as the module name from the start
3. Update go.mod immediately after `go mod init`:
   ```bash
   go mod edit -module=github.com/username/project-name
   ```
4. When updating import paths in files, use `sed` to replace all occurrences:
   ```bash
   sed -i '' 's|github.com/old/path|github.com/new/path|g' internal/**/*.go cmd/**/*.go
   ```

### GitHub License Not Applied via CLI
**Problem**: `gh repo create --license` flag doesn't exist in recent versions.

**Solution**: Create LICENSE file manually and push it:
```bash
cat > LICENSE << 'EOF'
MIT License
... standard MIT text with [year] and [fullname] ...
EOF
git add LICENSE && git commit -m "Add MIT license" && git push
```

### Go Sum Corruption
**Problem**: Running `go mod tidy` or `go mod vendor` can fail with "wrong number of fields" in go.sum.

**Solution**:
```bash
rm go.sum && go mod tidy && go mod vendor
```

### Dependencies with Invalid Transitive Dependencies
**Problem**: Some packages like `github.com/remyoudompheng/bigfft` may reference invalid versions.

**Solution**: Remove problematic indirect dependencies from go.mod manually and re-run `go mod tidy`.

### Docker Build Caching
**Problem**: Docker builds can be slow if not using build cache properly.

**Solution**: In Dockerfile, copy go.mod/go.sum first, run `go mod download`, THEN copy the rest of the files. This leverages Docker layer caching.

### GitHub Actions Cache for Go
**Problem**: Go builds in CI can be slow without caching.

**Solution**: Use GitHub Actions cache for Go modules:
```yaml
- uses: actions/cache@v4
  with:
    path: |
      ~/.cache/go-build
      ~/go/pkg/mod
    key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
    restore-keys: |
      ${{ runner.os }}-go-
```

### Module Version Auto-Upgrade
**Problem**: `go mod tidy` may auto-upgrade Go version (e.g., 1.22 → 1.24).

**Solution**:
- The version may be auto-updated by go tooling, which is generally fine for new projects
- Update Dockerfile to use matching Go version: `FROM golang:1.24-alpine`

### Skip go mod download When Vendoring
**Problem**: When using vendoring (`go mod vendor`), Docker build fails because `go mod download` is unnecessary and may fail if Go version doesn't match.

**Solution**:
- When vendoring is enabled, skip `go mod download` in Dockerfile
- Copy vendor directory before building
- Use `-mod vendor` flag in build commands:
```dockerfile
COPY vendor/ ./vendor/
RUN CGO_ENABLED=0 GOOS=linux go build -mod vendor -o server ./cmd/server
```

### Vendor Directory Not Found in Docker Build
**Problem**: Docker build fails with `"/vendor": not found` because vendor directory is in `.gitignore` and wasn't committed.

**Solution**:
1. Remove `vendor/` from `.gitignore`:
   ```
   # Go vendor (commented out to commit vendor directory)
   # vendor/
   ```
2. Commit and push the vendor directory:
   ```bash
   git add vendor/
   git commit -m "Add vendor directory for reproducible builds"
   git push
   ```
3. The vendor directory MUST be in the repository for Docker builds to work.

### Always Test Build Before Committing
**Problem**: Import path issues may only surface during `go build`.

**Solution**: Always run these commands before making the initial commit:
```bash
go mod tidy
go build ./cmd/server
go build ./cmd/bot
go mod vendor  # if vendoring enabled
```
