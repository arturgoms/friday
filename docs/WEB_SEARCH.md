# Friday AI - Automatic Web Search

## Overview
Friday now automatically detects when you need web search and uses it intelligently!

## How It Works

### Automatic Detection
Friday analyzes your message and automatically enables web search when you use certain keywords or patterns.

### Trigger Keywords

**Search Terms:**
- search, find, look up, google, web

**Time-Based:**
- latest, recent, current, news, today

**Question Words:**
- what is, who is, where is, when is, how to

**Specific Topics:**
- weather, forecast, stock, price
- happening, update, information about

### Smart Detection
Questions starting with "what/who/where/when/why/how" combined with general knowledge terms will trigger web search.

## Examples

### Will Use Web Search 🌐

```
"What's the latest news about AI?"
"Search for Python tutorials"
"What is the current weather in New York?"
"Who is the CEO of OpenAI?"
"Find information about Docker"
"What's happening in the tech world today?"
"Latest stock price for NVDA"
```

### Will NOT Use Web Search 📚

```
"What do my notes say about Django?"
"Summarize my meeting notes"
"What did I write about homelab setup?"
"Tell me about my Docker configuration"
```

## Visual Indicators

After each response, Friday shows what sources were used:

- 📚 **Notes** - Used your vault
- 💭 **Memory** - Used saved memories
- 🌐 **Web** - Used web search

Example:
```
[Response here]

📚 Notes + 🌐 Web
```

## Benefits

✅ **Automatic** - No need to specify when to search
✅ **Smart** - Uses context to decide
✅ **Fast** - Only searches when needed
✅ **Hybrid** - Can combine notes + web in one answer

## Commands

### Get Help
```
/help
```
Shows all available commands and web search info

### Check Stats
```
/stats
```
See system status

### Remember Something
```
/remember Your note here
```

## Configuration

Web search keywords are defined in `src/telegram_bot.py`:

```python
WEB_SEARCH_KEYWORDS = [
    'search', 'find', 'look up', 'google', 'web',
    'latest', 'recent', 'current', 'news', 'today',
    ...
]
```

To add more keywords, edit this list and restart the bot.

## Testing

After restarting the bot, try these:

```
"What's the latest news about Python?"  → Should use web 🌐
"What do my notes say about Python?"    → Should use notes 📚
```

Check the bot logs to see detection:
```bash
cd friday
./friday logs telegram_bot
```

You'll see: `[Web: True]` or `[Web: False]` in the logs.

## Restart Bot

To apply changes:
```bash
sudo systemctl restart telegram-bot.service
```

Or:
```bash
cd friday
./friday restart telegram-bot
```

## Tips

- Use natural language - the detection is smart
- Be specific about what you want (latest, current, etc.)
- Combine sources: "Search for latest Django tutorials and compare with my notes"
- Web searches take longer (up to 2 minutes timeout)

---

**Features:** Automatic web search detection
**Status:** Active
**Last Updated:** 2025-11-22
