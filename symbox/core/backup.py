import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class BackupManager:
    """Snapper-style git version control manager for Symbox snapshots."""

    def __init__(self, sbox_dir: str = "./.sbox"):
        self.sbox_dir = os.path.abspath(sbox_dir)
        self.backups_dir = os.path.join(self.sbox_dir, "backups")
        self.state_file = os.path.join(self.sbox_dir, "state.json")
        self._ensure_repo()

    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> str:
        cmd = ["git", f"--git-dir={self.backups_dir}", f"--work-tree={self.sbox_dir}"] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd or self.sbox_dir)
        if res.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\nStderr: {res.stderr.strip()}")
        return res.stdout.strip()

    def _ensure_repo(self) -> None:
        os.makedirs(self.sbox_dir, exist_ok=True)
        if not os.path.exists(self.backups_dir):
            os.makedirs(self.backups_dir, exist_ok=True)
            # Initialize bare git repository in backups_dir
            subprocess.run(["git", "init", "--bare", self.backups_dir], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Configure default user info for automatic commits
            self._run_git(["config", "user.name", "Symbox Backup Engine"])
            self._run_git(["config", "user.email", "symbox@agent.local"])

    def create(self, note: str) -> str:
        """Create a backup snapshot with specified note tag."""
        if not os.path.exists(self.state_file):
            # Create dummy initial state if not present
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({"subjects": {}, "verbs": {}, "svo": []}, f)

        # Add state.json to git index
        self._run_git(["add", "state.json"])
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        commit_msg = f"backup: {note} [{timestamp}]"
        
        # Commit
        commit_hash = self._run_git(["commit", "-m", commit_msg, "--allow-empty"]).splitlines()[-1]
        
        # Tag with note and commit hash if tag doesn't exist
        tag_name = note.replace(" ", "_")
        try:
            self._run_git(["tag", "-f", tag_name])
        except Exception:
            pass

        return tag_name

    def rollback(self, note_or_id: str) -> bool:
        """Rollback state to snapshot note or commit id."""
        tag_or_id = note_or_id.replace(" ", "_")
        try:
            # Checkout state.json from target commit/tag
            self._run_git(["checkout", tag_or_id, "--", "state.json"])
            return True
        except Exception as e:
            raise ValueError(f"Failed to rollback to backup '{note_or_id}': {e}")

    def delete(self, ids: List[str]) -> List[str]:
        """Delete backup tags/snapshots."""
        deleted = []
        for note_id in ids:
            tag_name = note_id.replace(" ", "_")
            try:
                self._run_git(["tag", "-d", tag_name])
                deleted.append(note_id)
            except Exception:
                pass
        return deleted

    def log(self) -> List[Dict[str, Any]]:
        """List backup snapshot history."""
        try:
            out = self._run_git(["log", "--pretty=format:%H|%s|%aI"])
            if not out:
                return []
            history = []
            for line in out.splitlines():
                if not line.strip():
                    continue
                parts = line.split("|")
                if len(parts) >= 3:
                    commit_hash, msg, iso_time = parts[0], parts[1], parts[2]
                    note = msg.replace("backup: ", "")
                    if " [" in note and note.endswith("]"):
                        note = note.rsplit(" [", 1)[0]
                    history.append({
                        "commit": commit_hash[:8],
                        "note": note,
                        "timestamp": iso_time,
                    })
            return history
        except Exception:
            return []
