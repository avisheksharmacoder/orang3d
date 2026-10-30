#!/usr/bin/env python3
"""
orang3D Cross-Platform Standalone Build & Packaging Script.
Builds standalone, portable application packages for Windows or Linux.

Usage:
    python scripts/build_executable.py
    python scripts/build_executable.py --onefile
    python scripts/build_executable.py --clean --archive
"""

import os
import sys
import shutil
import platform
import argparse
import subprocess
import tarfile
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build and package orang3D standalone distribution.")
    parser.add_argument("--onefile", action="store_true", help="Build single-file executable instead of directory bundle.")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean build directories before packaging.")
    parser.add_argument("--archive", action="store_true", default=True, help="Create distribution zip/tar.gz archive.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    print("=" * 70)
    print("orang3D Standalone Executable Packaging Engine")
    print(f"Platform: {platform.system()} ({platform.machine()})")
    print(f"Python:   {sys.version.split()[0]}")
    print(f"Mode:     {'Single-File' if args.onefile else 'Directory Bundle (Recommended)'}")
    print("=" * 70)

    # 1. Ensure resources & icons exist
    icon_script = project_root / "scripts" / "generate_icon.py"
    if icon_script.is_file():
        print("[1/5] Checking / generating application icons...")
        subprocess.run([sys.executable, str(icon_script)], check=True)

    # 2. Clean previous build artifacts if requested
    if args.clean:
        print("[2/5] Cleaning previous build/dist caches...")
        for p in ["build", "dist"]:
            if os.path.exists(p):
                shutil.rmtree(p, ignore_errors=True)

    # 3. Configure environment
    env = os.environ.copy()
    if args.onefile:
        env["ORANG3D_ONEFILE"] = "1"
    else:
        env["ORANG3D_ONEFILE"] = "0"

    # 4. Invoke PyInstaller
    spec_path = project_root / "orang3d.spec"
    print(f"[3/5] Running PyInstaller on {spec_path.name}...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_path),
    ]
    if args.clean:
        cmd.append("--clean")

    res = subprocess.run(cmd, env=env)
    if res.returncode != 0:
        print("ERROR: PyInstaller build failed!")
        sys.exit(res.returncode)

    print("[4/5] Build succeeded!")

    # 5. Archive package for distribution
    if args.archive:
        print("[5/5] Packaging distribution archive...")
        dist_dir = project_root / "dist"
        system_name = platform.system().lower()
        arch = platform.machine().lower()

        if system_name == "windows":
            archive_name = f"orang3d-windows-{arch}.zip"
            archive_path = dist_dir / archive_name
            target = dist_dir / "orang3d"

            if args.onefile:
                exe_target = dist_dir / "orang3d.exe"
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(exe_target, arcname="orang3d.exe")
                    if os.path.exists("README.md"):
                        zf.write("README.md", arcname="README.md")
            else:
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(target):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, dist_dir)
                            zf.write(full_path, arcname=rel_path)
            print(f"--> Created Windows distribution package: {archive_path}")

        else:
            # Linux / Unix
            archive_name = f"orang3d-linux-{arch}.tar.gz"
            archive_path = dist_dir / archive_name
            target = dist_dir / "orang3d"

            if args.onefile:
                bin_target = dist_dir / "orang3d"
                with tarfile.open(archive_path, "w:gz") as tf:
                    tf.add(bin_target, arcname="orang3d")
                    if os.path.exists("README.md"):
                        tf.add("README.md", arcname="README.md")
                    if os.path.exists("resources/orang3d.desktop"):
                        tf.add("resources/orang3d.desktop", arcname="orang3d.desktop")
            else:
                # Include desktop file in onedir bundle
                if os.path.exists("resources/orang3d.desktop"):
                    shutil.copy("resources/orang3d.desktop", target / "orang3d.desktop")
                if os.path.exists("README.md"):
                    shutil.copy("README.md", target / "README.md")

                with tarfile.open(archive_path, "w:gz") as tf:
                    tf.add(target, arcname="orang3d")
            print(f"--> Created Linux distribution package: {archive_path}")

    print("=" * 70)
    print("SUCCESS: orang3D export build completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
