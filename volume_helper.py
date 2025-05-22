import os

def get_volume_path(filename: str) -> str:
    # Replit has no special volume dir, so store in local `data` folder
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)
