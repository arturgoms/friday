# Vault Sync: Making Manual Edits Searchable

## The Problem

When you manually edit facts in your Obsidian vault, they're **not automatically indexed** for semantic search. This means:

❌ You add `favorite_book: "Dune"` to `Artur Gomes.md`  
❌ Friday can't find it with semantic search  
❌ Queries like "what books do I like?" won't find it  

## The Solution: `facts-sync`

The `facts-sync` command scans your vault and indexes facts into the database, making them searchable.

### How It Works

```bash
# Preview what would be synced (safe, no changes)
./friday facts-sync --dry-run

# Sync new facts from vault to database
./friday facts-sync

# Re-sync everything (useful after bulk vault edits)
./friday facts-sync --force
```

### What Gets Synced

**1. User Attributes (`Artur Gomes.md`)**
- Any field matching `USER_ATTRIBUTES` (favorite_*, preferred_*, etc.)
- Examples: `favorite_color`, `favorite_book`, `favorite_food`

**2. Person Facts (All person notes)**
- Fields: `birthday`, `email`, `phone`, `relationship`
- Format: `{person_name}_{field}` (e.g., `camila_santos_birthday`)
- Automatically categorized by tags

**3. NOT Synced (by design)**
- Friday.md observations (already indexed when Friday saves them)
- Non-person notes
- Fields that aren't standard attributes

### Example Workflow

```bash
# 1. You manually edit your vault
vim brain/1. Notes/Artur\ Gomes.md

# Add:
---
favorite_book: "Dune"
favorite_movie: "Blade Runner"
---

# 2. Preview what would be synced
./friday facts-sync --dry-run

# Output:
# Found 2 facts to sync
# Would sync:
#   • favorite_book: Dune
#   • favorite_movie: Blade Runner

# 3. Sync to make them searchable
./friday facts-sync

# ✓ Successfully synced 2/2 facts!
# Your vault facts are now searchable with semantic search.

# 4. Verify they're indexed
./friday facts-search "movies"

# Found 1 fact matching 'movies':
# • favorite_movie: Blade Runner
```

## Automatic vs Manual Indexing

### ✅ Automatic (No Sync Needed)
When Friday saves facts, they're automatically indexed:
- You: "My favorite color is black"
- Friday saves to vault **AND** indexes in DB
- Immediately searchable

### 🔄 Manual Sync Required
When you edit the vault directly:
- You manually add `favorite_book: "Dune"` to vault
- **Not indexed** until you run `./friday facts-sync`
- After sync, becomes searchable

## Sync Details

### What Happens During Sync

1. **Scans vault notes**
   - `Artur Gomes.md` for user attributes
   - All person notes for contact/relationship info

2. **Extracts facts**
   - Reads frontmatter YAML
   - Identifies relevant fields

3. **Generates embeddings**
   - Creates 384-dim vectors for semantic search
   - Uses sentence-transformers model

4. **Indexes in database**
   - Stores in `~/friday_facts.db`
   - Links back to vault location
   - Enables semantic search

### Database Structure

Each synced fact includes:
- `topic` - Fact identifier (e.g., "favorite_book")
- `value` - The actual data (e.g., "Dune")
- `category` - Auto-categorized (preferences, family, contacts)
- `vault_path` - Source file path
- `vault_field` - Frontmatter field name
- `embedding` - Vector for semantic search
- `source` - Set to "vault_sync"

## Semantic Search

After syncing, facts become searchable by meaning, not just keywords:

```bash
# Query: "What books do I like?"
# Finds: favorite_book: "Dune"
# (even though "books" ≠ "book")

# Query: "Tell me about my family"
# Finds: wife_name, wife_birthday, sister info, etc.
# (semantic match on "family")
```

## When to Sync

Run `facts-sync` after:
- ✅ Bulk editing vault notes
- ✅ Importing person notes from another system
- ✅ Manually adding new person notes
- ✅ Updating birthdays, emails, phones in vault

No need to sync after:
- ❌ Friday saves a fact (already indexed)
- ❌ Reading vault notes (no changes)

## Example: Real Sync Output

```bash
$ ./friday facts-sync --dry-run

Scanning Obsidian vault for facts...

📄 Scanning Artur Gomes.md...

📄 Scanning person notes...
  📝 Sofia Menezes
    → Found: sofia_menezes_birthday = 2001-10-26
    → Found: sofia_menezes_email = ['sofiamatos10@hotmail.com']
    → Found: sofia_menezes_phone = +54 9 11 33532888
  📝 Camila Santos
    → Found: camila_santos_birthday = 1995-12-12
    → Found: camila_santos_email = ['camilafds1995@gmail.com']
    → Found: camila_santos_phone = +55 41 999182344

============================================================
Found 6 facts to sync

DRY RUN - No changes made
```

## CLI Reference

```bash
# Sync commands
./friday facts-sync              # Sync new facts
./friday facts-sync --dry-run    # Preview only
./friday facts-sync --force      # Re-sync everything

# Verify synced facts
./friday facts-list              # List all (shows vault location)
./friday facts-search <query>    # Search with semantic fallback

# Manage embeddings
./friday facts-reindex           # Regenerate embeddings
./friday facts-reindex --force   # Reindex all facts
```

## Files

- **Command:** `src/cli.py::facts_sync()`
- **Vault integration:** `src/core/vault.py`
- **Database:** `~/friday_facts.db`
- **Embeddings model:** sentence-transformers (384-dim)

## Summary

**Before sync:**
- Manual vault edits → Not searchable
- `get_fact("favorite_book")` → Not found

**After sync:**
- Manual vault edits → Indexed in DB
- `get_fact("favorite_book")` → Found: "Dune"
- Semantic search works
- `facts-list` shows vault location

**Key command:**
```bash
./friday facts-sync
```

Makes your manual vault edits discoverable! 🔍
