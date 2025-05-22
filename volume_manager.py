import os
import argparse
import shutil
import time
from volume_helper import get_volume_path


def list_json_files():
    volume_dir = os.path.dirname(get_volume_path("dummy.json"))
    files = [f for f in os.listdir(volume_dir) if f.endswith('.json')]
    if not files:
        print("No JSON files found in volume.")
    else:
        print("JSON files in volume:")
        for f in files:
            print(f"- {f}")


def download_file(filename):
    src_path = get_volume_path(filename)
    if not os.path.exists(src_path):
        print(f"❌ File {filename} not found in volume.")
        return
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest_filename = filename
    if os.path.exists(filename):
        dest_filename = f"{filename}.DOWNLOADED_{timestamp}"
    shutil.copy(src_path, dest_filename)
    print(f"✅ Downloaded {filename} to local file {dest_filename}.")


def upload_file(localfile):
    if not os.path.exists(localfile):
        print(f"❌ Local file {localfile} does not exist.")
        return
    dest_path = get_volume_path(os.path.basename(localfile))
    if os.path.exists(dest_path):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = f"{dest_path}.bak_{timestamp}"
        shutil.copy(dest_path, backup_path)
        print(f"🔒 Existing file backed up as {backup_path}.")
    shutil.copy(localfile, dest_path)
    print(f"✅ Uploaded {localfile} to volume as {os.path.basename(localfile)}.")


def main():
    parser = argparse.ArgumentParser(description="Manage JSON files in Railway volume.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all JSON files in the volume.")

    download_parser = subparsers.add_parser("download", help="Download JSON file from volume.")
    download_parser.add_argument("filename", help="Name of the JSON file to download.")

    upload_parser = subparsers.add_parser("upload", help="Upload JSON file to volume.")
    upload_parser.add_argument("localfile", help="Path to local JSON file to upload.")

    args = parser.parse_args()

    if args.command == "list":
        list_json_files()
    elif args.command == "download":
        download_file(args.filename)
    elif args.command == "upload":
        upload_file(args.localfile)


if __name__ == "__main__":
    main()
