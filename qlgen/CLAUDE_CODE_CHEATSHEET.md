# Claude Code Cheat Sheet

## Keyboard Shortcuts

### Core Controls
| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Cancel current input/generation |
| `Ctrl+D` | Exit Claude Code |
| `Ctrl+L` | Clear prompt input (keeps history) |
| `Ctrl+O` | Toggle transcript viewer |
| `Ctrl+R` | Reverse search command history |
| `Ctrl+B` | Background running task |
| `Ctrl+T` | Toggle task list |
| `Ctrl+X Ctrl+K` | Kill all background agents (press twice) |
| `Esc Esc` | Rewind / summarize |
| `Shift+Tab` | Cycle permission modes |

### Mode Switching
| Shortcut | Action |
|----------|--------|
| `Alt+P` | Switch model |
| `Alt+T` | Toggle extended thinking |
| `Alt+O` | Toggle fast mode |
| `Shift+Tab` / `Alt+M` | Cycle permission modes |

### Input
| Shortcut | Action |
|----------|--------|
| `\` + `Enter` | New line (quick) |
| `Shift+Enter` | New line |
| `Ctrl+J` | New line |
| `Ctrl+G` | Open in external editor |
| `Space` (hold) | Push-to-talk dictation |
| `/` | Open command menu |
| `!` | Bash mode (run shell command directly) |
| `@` | File/directory autocomplete |

### Text Editing
| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Delete to end of line |
| `Ctrl+U` | Delete to start of line |
| `Ctrl+Y` | Paste deleted text |
| `Alt+B` / `Alt+F` | Move word back / forward |

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/clear` | New session (history preserved) |
| `/compact` | Compress context window |
| `/config` | Open settings UI |
| `/cost` | View API usage/costs |
| `/doctor` | Run diagnostics |
| `/effort` | Set effort level (low/medium/high/max) |
| `/hooks` | View/manage hooks |
| `/init` | Initialize CLAUDE.md |
| `/login` / `/logout` | Auth management |
| `/mcp` | Configure MCP servers |
| `/memory` | Manage CLAUDE.md and memory files |
| `/model` | Switch model |
| `/permissions` | View/manage permissions |
| `/plugins` | Manage plugins |
| `/rename [name]` | Rename session |
| `/resume [id]` | Resume previous session |
| `/rewind` | Restore to previous checkpoint |
| `/status` | Session status |
| `/terminal-setup` | Configure terminal for keybindings |
| `/vim` | Enable vim mode |
| `/add-dir [path]` | Add working directory |
| `/btw [question]` | Quick side question (no history) |

### Bundled Skills
| Command | Description |
|---------|-------------|
| `/simplify` | Review code for quality/efficiency |
| `/loop [interval] [cmd]` | Run prompt on recurring interval |
| `/batch` | Execute changes in parallel worktrees |
| `/debug` | Enable debug logging |

---

## CLI Flags

### Session
```bash
claude                           # Interactive session
claude "prompt"                  # Start with prompt
claude -p "prompt"               # Print mode (query & exit)
claude -c / --continue           # Continue last session
claude -r / --resume [id/name]   # Resume specific session
claude --from-pr 123             # Resume PR-linked session
claude -n "name"                 # Name the session
claude -w "name"                 # Create isolated worktree
claude -w "name" --tmux          # Worktree + tmux session
```

### Model & Effort
```bash
claude --model claude-opus-4-6
claude --effort high
claude --agent my-agent
```

### Permissions
```bash
claude --permission-mode plan
claude --allowedTools "Bash(git *)" "Read"
claude --disallowedTools "Bash(rm *)"
claude --dangerously-skip-permissions    # Use with caution!
```

### System Prompt
```bash
claude --system-prompt "You are a Python expert"
claude --system-prompt-file ./prompt.txt
claude --append-system-prompt "Always test code"
```

### Output
```bash
claude -p --output-format json "query"
claude -p --output-format stream-json "query"
claude -p --json-schema '{"type":"object"...}' "query"
```

### Limits
```bash
claude -p --max-turns 3 "query"
claude -p --max-budget-usd 5.00 "query"
claude --fallback-model sonnet
```

### MCP & Plugins
```bash
claude --mcp-config ./mcp.json
claude --strict-mcp-config --mcp-config ./mcp.json
claude --plugin-dir ./plugins
```

### Other
```bash
claude --bare                    # Minimal startup
claude --verbose                 # Verbose logging
claude --debug "api,mcp"         # Debug categories
claude --add-dir ../lib          # Extra directories
claude --remote "Fix bug"        # Web session on claude.ai
claude --remote-control          # Enable Remote Control
claude -v / --version            # Show version
claude update                    # Update Claude Code
```

### Auth Commands
```bash
claude auth login                # Sign in
claude auth login --sso          # SSO sign in
claude auth logout               # Sign out
claude auth status               # Show auth status (JSON)
claude auth status --text        # Show auth status (readable)
claude setup-token               # Generate CI token
```

---

## Permission Modes

| Mode | Behavior |
|------|----------|
| `default` | Prompts for each new tool |
| `acceptEdits` | Auto-approves file operations |
| `plan` | Describes plan before executing |
| `auto` | Classifier decides (research preview) |
| `dontAsk` | Only runs pre-approved tools |
| `bypassPermissions` | Skips all prompts (sandbox only) |

Cycle: `Shift+Tab` in interactive mode

---

## Permission Rules Syntax

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(git commit *)",
      "Read",
      "Edit(/src/**)"
    ],
    "ask": [
      "Bash(docker *)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Edit(.env)"
    ]
  }
}
```

**Patterns:** `Bash(npm *)` (prefix), `Bash(* install)` (suffix), `WebFetch(domain:example.com)`, `mcp__server__tool`

**Path patterns:** `//absolute`, `~/home`, `/project-relative`, `./cwd-relative`, `**` recursive

---

## Settings & Configuration

### File Locations (precedence order)
| Level | Path | Shared? |
|-------|------|---------|
| Managed | Server/MDM | Enforced |
| User | `~/.claude/settings.json` | No |
| Project | `.claude/settings.json` | Yes (git) |
| Local | `.claude/settings.local.json` | No (gitignored) |

### Key Settings
```json
{
  "defaultMode": "plan",
  "alwaysThinkingEnabled": true,
  "showThinkingSummaries": false,
  "additionalDirectories": ["/path"],
  "env": { "KEY": "value" },
  "permissions": { "allow": [], "ask": [], "deny": [] },
  "hooks": { "PreToolUse": [...] },
  "MCP": [...]
}
```

---

## Hooks

### Events
| Event | Trigger |
|-------|---------|
| `SessionStart` / `SessionEnd` | Session lifecycle |
| `UserPromptSubmit` | Before processing prompt |
| `PreToolUse` | Before tool runs (can block) |
| `PostToolUse` | After tool succeeds |
| `Stop` / `StopFailure` | Before/after tool execution |
| `Notification` | When Claude needs attention |
| `FileChanged` | File modified |

### Configuration
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/script.sh"
          }
        ]
      }
    ]
  }
}
```

**Hook types:** `command` (shell), `http` (POST), `prompt` (LLM), `agent` (subagent)
**Exit codes:** 0 = success, 2 = block, other = non-blocking error

---

## MCP Server Setup

```bash
# Add servers
claude mcp add --transport http github https://api.example.com/mcp/
claude mcp add --transport stdio sqlite file:///path/to/sqlite.exe
claude mcp add --transport sse postgres http://localhost:3000/sse
```

```json
{
  "mcp": [
    {
      "name": "github",
      "transport": "http",
      "url": "https://api.example.com/mcp/"
    }
  ]
}
```

---

## Environment Variables

### Auth & API
| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key |
| `ANTHROPIC_BASE_URL` | Override API endpoint |
| `ANTHROPIC_MODEL` | Default model |

### Cloud Providers
| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_USE_BEDROCK` | Use AWS Bedrock |
| `ANTHROPIC_BEDROCK_BASE_URL` | Bedrock endpoint |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Google Vertex project |

### Effort & Thinking
| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_EFFORT_LEVEL` | low / medium / high / max |
| `MAX_THINKING_TOKENS` | Limit thinking budget |
| `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` | Disable adaptive reasoning |

### Performance
| Variable | Default | Description |
|----------|---------|-------------|
| `API_TIMEOUT_MS` | 600000 | API timeout (ms) |
| `BASH_DEFAULT_TIMEOUT_MS` | 120000 | Bash timeout (ms) |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | varies | Output token limit |

### Feature Flags
| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_DISABLE_FAST_MODE` | Disable fast mode |
| `CLAUDE_CODE_DISABLE_THINKING` | Disable extended thinking |
| `DISABLE_AUTO_COMPACT` | Disable auto-compaction |
| `NO_COLOR` | Disable colored output |

---

## IDE Integration (VS Code)

### Shortcuts
| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl+Esc` | Focus Claude input |
| `Cmd/Ctrl+Shift+Esc` | Open Claude in new tab |
| `Alt+K` | Insert @-mention |
| `Cmd/Ctrl+N` | New conversation |

### @-Mentions
```
@file.ts              # Single file
@src/components/      # Directory
@file.ts#5-10         # Line range
@browser              # Browser tools
```

---

## Project File Structure

```
project-root/
├── CLAUDE.md                      # Project instructions (auto-loaded)
├── .claude/
│   ├── settings.json              # Shared project config
│   ├── settings.local.json        # Personal config (gitignored)
│   ├── agents/                    # Custom subagents
│   │   └── my-agent/agent.md
│   ├── skills/                    # Custom skills
│   │   └── my-skill/SKILL.md
│   └── hooks/                     # Hook scripts
├── .worktreeinclude               # Files to copy to worktrees
│
~/.claude/
├── settings.json                  # User-level config
├── keybindings.json               # Custom keybindings
├── agents/                        # Personal subagents
└── skills/                        # Personal skills
```

---

## Common Workflows

### Quick Analysis
```bash
claude -p "explain this codebase" > overview.txt
claude -p --output-format json "list all API endpoints" > endpoints.json
```

### Safe Exploration
```bash
claude --permission-mode plan      # Plan mode: see before execute
```

### Parallel Work
```bash
claude -w feature-auth             # Isolated worktree
claude -w bugfix-123 --tmux        # Worktree + tmux
```

### Context Management
```
/compact                           # Compress context
/clear                             # Fresh start
/rewind                            # Undo to checkpoint
```

### Extended Thinking
Include "ultrathink" in prompt for maximum reasoning depth.
