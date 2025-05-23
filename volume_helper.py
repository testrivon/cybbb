import os

# Change this if your Northflank mount point is different
VOLUME_MOUNT_PATH = "/data"

def get_volume_path(filename: str) -> str:
    """Get the full path to a file in the mounted volume."""
    path = os.path.join(VOLUME_MOUNT_PATH, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path
