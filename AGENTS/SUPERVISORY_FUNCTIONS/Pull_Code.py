import subprocess
import time
import os

def PULL_FUNCTION(repo_path, log_path):
    """Continuously check for changes in the repository and log messages."""
    try:
        while True:
            # Ensure the current branch is tracking a remote branch
            setup_tracking_branch(repo_path, log_path)

            # Fetch the latest changes from the remote repository
            fetch_result = subprocess.run(
                ["git", "fetch"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            # Check the status of the repository
            status_result = subprocess.run(
                ["git", "status", "-uno"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            if "Your branch is up to date" in status_result.stdout:
                log_message(log_path, "No changes for the past minute.")
            else:
                log_message(log_path, "Changes detected. Pulling updates...")
                pull_result = subprocess.run(
                    ["git", "pull"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                log_message(log_path, "New Changes Pulled.")

                # Sync the folders after pulling updates
                sync_folders(repo_path, "/home/taha", log_path)

            # Wait for 60 seconds before checking again
            time.sleep(60)

    except subprocess.CalledProcessError as e:
        log_message(log_path, f"An error occurred: {e}")
    except Exception as e:
        log_message(log_path, f"Unexpected error: {e}")


def setup_tracking_branch(repo_path, log_path):
    """Ensure the current branch is tracking the correct remote branch."""
    # Check if the branch is already tracking
    branch_result = subprocess.run(
        ["git", "branch", "-vv"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    if "[origin/" not in branch_result.stdout:
        # Set the upstream branch to origin/main
        set_tracking_result = subprocess.run(
            ["git", "branch", "--set-upstream-to=origin/main", "main"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )


def log_message(log_path, message):
    """Log a message to the specified log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())  # Print the message to the console for visibility
    with open(log_path, "a") as log_file:
        log_file.write(log_entry)


def sync_folders(source_base, target_base, log_path):
    """Synchronize specific folders from the repository to the target directory."""
    folders_to_sync = ["AGENTS","DSO_IN"]  # Update as per your folder names

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


# Set the path to your local repository and log file
repo_path = "/home/taha/Inverter_1"
log_path = "/home/taha/github_log.log"

# Run the function
PULL_FUNCTION(repo_path, log_path)

