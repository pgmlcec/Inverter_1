import subprocess
import time
import os

def PUSH_CODE(repo_path, log_path):
    """Continuously check for changes in the source folder, sync, and push updates to GitHub."""
    try:
        while True:
            # Synchronize the folders
            log_message(log_path, "Syncing folders...")
            sync_folders(repo_path, "/home/taha", log_path)

            # Check the repository status
            status_result = subprocess.run(
                ["git", "status", "-s"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            if not status_result.stdout.strip():
                log_message(log_path, "No changes to commit.")
            else:
                log_message(log_path, "Changes detected. Adding, committing, and pushing updates...")

                # Add changes to staging
                subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, text=True)

                # Commit changes
                commit_message = f"Auto-update: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
                subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_path, capture_output=True, text=True)

                # Pull the latest changes from the remote branch to avoid conflicts
                pull_result = subprocess.run(
                    ["git", "pull", "--rebase"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                if pull_result.returncode != 0:
                    log_message(log_path, f"Error pulling changes: {pull_result.stderr}")
                    continue

                # Push changes to GitHub
                push_result = subprocess.run(
                    ["git", "push"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )

                if push_result.returncode == 0:
                    log_message(log_path, "Changes pushed successfully.")
                else:
                    log_message(log_path, f"Error pushing changes: {push_result.stderr}")

            # Wait for 60 seconds before checking again
            time.sleep(60)

    except subprocess.CalledProcessError as e:
        log_message(log_path, f"An error occurred: {e}")
    except Exception as e:
        log_message(log_path, f"Unexpected error: {e}")

def log_message(log_path, message):
    """Log a message to the specified log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())  # Print the message to the console for visibility
    with open(log_path, "a") as log_file:
        log_file.write(log_entry)

def sync_folders(target_base, source_base, log_path):
    """Synchronize specific folders from the repository to the target directory."""
    folders_to_sync = ["Supervisory_Logs"]  # Update as per your folder names

    for folder in folders_to_sync:
    
        source = os.path.join(source_base, folder)
        target = os.path.join(target_base, folder)

        if os.path.exists(source):
            # Create the target directory if it doesn't exist
            os.makedirs(target, exist_ok=True)

            # Use rsync to sync the folder
            sync_result = subprocess.run(
                ["rsync", "-av", "--delete", source + "/", target],
                capture_output=True,
                text=True
            )

            if sync_result.returncode == 0:
                log_message(log_path, f"Successfully synced {folder} to {target}.")
            else:
                log_message(log_path, f"Error syncing {folder}: {sync_result.stderr}")
        else:
            log_message(log_path, f"Source folder {source} does not exist.")


# Set the path to your source and target directories and log file

repo_path = "/home/taha/Inverter_1"
log_path = "/home/taha/github_push_log.log"

# Run the function
PUSH_CODE(repo_path, log_path)

