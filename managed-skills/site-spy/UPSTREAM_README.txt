Title: @site-spy/mcp-server

URL Source: https://www.npmjs.com/package/@site-spy/mcp-server

Markdown Content:
MCP server that lets AI agents monitor websites for changes via [Site Spy](https://sitespy.app/).

Track pages, get notified when content changes, view diffs and snapshots — all from your AI assistant.

Add to your AI client config:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

{
  "mcpServers": {
    "site-spy": {
      "command": "npx",
      "args": ["-y", "@site-spy/mcp-server"],
      "env": {
        "SITE_SPY_API_KEY": "your-api-key"
      }
    }
  }
}

**Claude Code** (`.mcp.json`):

{
  "mcpServers": {
    "site-spy": {
      "command": "npx",
      "args": ["-y", "@site-spy/mcp-server"],
      "env": {
        "SITE_SPY_API_KEY": "your-api-key"
      }
    }
  }
}

**Cursor** (`.cursor/mcp.json`):

{
  "mcpServers": {
    "site-spy": {
      "command": "npx",
      "args": ["-y", "@site-spy/mcp-server"],
      "env": {
        "SITE_SPY_API_KEY": "your-api-key"
      }
    }
  }
}

Get your API key from [Site Spy Dashboard](https://sitespy.app/dashboard/settings?tab=api) → Settings → API.

If you don't set `SITE_SPY_API_KEY`, the agent will ask you to authenticate interactively.

| Tool | Description |
| --- | --- |
| `authenticate` | Connect with an API key (if not set via env var) |
| `auth_status` | Check authentication status |

| Tool | Description |
| --- | --- |
| `list_watches` | List all monitored websites (optionally filter by tag) |
| `create_watch` | Start monitoring a URL for changes |
| `get_watch` | Get full details of a specific watch |
| `update_watch` | Update config — pause/resume, change interval, rename |
| `delete_watch` | Stop monitoring and delete a watch |
| `search_watches` | Search watches by URL or title |
| `trigger_recheck` | Force an immediate recheck of all watches |

| Tool | Description |
| --- | --- |
| `get_change_history` | Get timestamps of detected changes |
| `get_snapshot` | Get page content at a specific timestamp |
| `get_diff` | Compare content between two timestamps |

| Tool | Description |
| --- | --- |
| `get_rss_settings` | Get current RSS feed settings and token |
| `generate_rss_token` | Generate or regenerate an RSS feed token for feed URLs |
| `revoke_rss_token` | Revoke the RSS token, disabling all feed access |

| Tool | Description |
| --- | --- |
| `list_tags` | List all tags for organizing watches |
| `get_notifications` | Get current notification settings |

Site Spy provides per-user RSS feeds so you can subscribe to change notifications in any RSS reader.

Once you have a token (via `generate_rss_token`), feed URLs follow this pattern:

*   **All watches**: `https://sitespy.app/api/rss?token={token}`
*   **Single watch**: `https://sitespy.app/api/rss/watch/{watch_uuid}?token={token}`
*   **By tag**: `https://sitespy.app/api/rss/tag/{tag_uuid}?token={token}`

| Variable | Description | Default |
| --- | --- | --- |
| `SITE_SPY_API_KEY` | API key for authentication | — (interactive auth) |
| `SITE_SPY_API_URL` | Backend API URL | `https://detect.coolify.vkuprin.com/api/v1` |
| `SITE_SPY_AUTH_URL` | URL shown to users for getting API keys | `https://sitespy.app/dashboard` |

Full documentation is available at [docs.sitespy.app](https://docs.sitespy.app/).

Once configured, try asking your AI assistant:

*   "Monitor [https://example.com](https://example.com/) for changes every 30 minutes"
*   "What websites am I monitoring?"
*   "Show me what changed on my watched pages"
*   "Pause all monitors tagged 'staging'"
*   "Check all my sites right now"
*   "Set up RSS feeds so I can follow changes in my feed reader"

ISC
