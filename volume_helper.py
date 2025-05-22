import os

def get_volume_path(filename: str, fallback_dir: str = "local_data") -> str:
    """
    Returns a file path inside a Railway volume if it exists, otherwise a local fallback.
    """
    volume_mount = os.getenv("VOLUME_PATH", "/data")
    target_dir = volume_mount if os.path.exists(volume_mount) else fallback_dir
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, filename)