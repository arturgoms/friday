# Nextcloud Sync Setup for Friday

This guide will help you mount your Nextcloud Obsidian vault so Friday can sync across all your devices.

## Option 1: WebDAV Mount (Recommended)

### Step 1: Install davfs2

```bash
sudo bash /home/artur/friday/setup_nextcloud_sync.sh
```

This will:
- Install davfs2
- Configure it for user mounting
- Add you to the davfs2 group
- Create mount point at `/home/artur/nextcloud-obsidian`

**IMPORTANT**: Log out and back in after this step for group changes to take effect.

### Step 2: Get Your Nextcloud WebDAV URL

1. Log into your Nextcloud web interface
2. Go to Settings → Security
3. Create an "App password" for Friday (recommended for security)
4. Your WebDAV URL format is:
   ```
   https://YOUR-NEXTCLOUD-DOMAIN/remote.php/dav/files/YOUR-USERNAME/PATH-TO-OBSIDIAN
   ```

Example:
```
https://cloud.example.com/remote.php/dav/files/artur/Documents/my-brain
```

### Step 3: Create Credentials File

```bash
mkdir -p ~/.davfs2
nano ~/.davfs2/secrets
```

Add this line (replace with your details):
```
https://YOUR-NEXTCLOUD-DOMAIN/remote.php/dav/files/YOUR-USERNAME/PATH-TO-OBSIDIAN your-email@example.com your-app-password
```

Set permissions:
```bash
chmod 600 ~/.davfs2/secrets
```

### Step 4: Test Manual Mount

```bash
mount -t davfs https://YOUR-NEXTCLOUD-URL /home/artur/nextcloud-obsidian
```

Check if it works:
```bash
ls /home/artur/nextcloud-obsidian
```

Unmount:
```bash
umount /home/artur/nextcloud-obsidian
```

### Step 5: Configure Auto-Mount

Edit `/etc/fstab`:
```bash
sudo nano /etc/fstab
```

Add this line:
```
https://YOUR-NEXTCLOUD-URL /home/artur/nextcloud-obsidian davfs user,rw,auto,uid=artur,gid=artur 0 0
```

Mount it:
```bash
mount /home/artur/nextcloud-obsidian
```

### Step 6: Point Friday to Nextcloud Vault

Stop Friday:
```bash
pkill -f "python main.py"
```

Edit `.env`:
```bash
nano /home/artur/friday/.env
```

Update or add:
```
VAULT_PATH=/home/artur/nextcloud-obsidian
MEMORY_PATH=/home/artur/nextcloud-obsidian/1. Notes
```

Restart Friday:
```bash
cd /home/artur/friday
./run.sh
```

### Step 7: Verify

```bash
curl http://localhost:8080/health | python3 -m json.tool
```

Should show your Nextcloud vault path.

---

## Option 2: Nextcloud Desktop Client (Alternative)

If you prefer a GUI:

1. Install Nextcloud desktop client:
   ```bash
   sudo add-apt-repository ppa:nextcloud-devs/client
   sudo apt update
   sudo apt install nextcloud-desktop
   ```

2. Configure sync folder (e.g., `/home/artur/Nextcloud`)

3. Create symlink:
   ```bash
   ln -s /home/artur/Nextcloud/my-brain /home/artur/my-brain-nextcloud
   ```

4. Update Friday's `.env` to point to the sync folder

---

## Option 3: Rclone (Advanced)

For more advanced setups with caching:

```bash
sudo apt install rclone
rclone config  # Configure Nextcloud WebDAV

# Mount with caching
rclone mount nextcloud:my-brain /home/artur/nextcloud-obsidian \
  --vfs-cache-mode full \
  --daemon
```

---

## Quick Fix for "malformed line" Error

If you get `/sbin/mount.davfs:/etc/davfs2/davfs2.conf:78: malformed line`:

```bash
# Fix the config file
sudo bash /home/artur/friday/fix_davfs_config.sh
```

This happens when `user_allow_other` was added incorrectly. The script will:
1. Backup your config
2. Remove duplicate/malformed entries
3. Add `user_allow_other` correctly

## Troubleshooting

### WebDAV mount issues

1. Check credentials:
   ```bash
   cat ~/.davfs2/secrets
   ```

2. Test connection:
   ```bash
   curl -u "user:pass" https://YOUR-NEXTCLOUD-URL
   ```

3. Check mount logs:
   ```bash
   tail -f /var/log/syslog | grep davfs
   ```

### Friday not seeing files

1. Check vault path:
   ```bash
   curl http://localhost:8080/admin/debug | python3 -m json.tool
   ```

2. Manually trigger reindex:
   ```bash
   curl -X POST http://localhost:8080/admin/reindex
   ```

3. Check Friday logs:
   ```bash
   tail -f /home/artur/friday/friday.log
   ```

### File watcher not working on mounted filesystem

Some network filesystems don't support inotify. If auto-indexing doesn't work:

1. Disable file watcher
2. Add a cron job to periodically reindex:
   ```bash
   */5 * * * * curl -X POST http://localhost:8080/admin/reindex
   ```

---

## Security Notes

1. **Always use app passwords**, not your main Nextcloud password
2. Keep `~/.davfs2/secrets` permissions at 600
3. Consider using HTTPS only
4. If exposing Friday API, set `FRIDAY_API_KEY` in `.env`

---

## Performance Tips

1. **Enable VFS caching** if using rclone
2. **Disable file watcher** on slow network mounts (use periodic reindex)
3. **Use local cache** for frequently accessed files
4. **Mount only the Obsidian vault**, not entire Nextcloud

---

## Current Setup

Your current vault: `/home/artur/my-brain` (local)

After setup, Friday will:
- ✅ Watch your Nextcloud-synced vault
- ✅ Auto-index changes from any device
- ✅ Create memories directly in Nextcloud
- ✅ Sync RAG index across all your devices
