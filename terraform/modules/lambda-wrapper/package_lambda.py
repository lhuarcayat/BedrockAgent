import sys, shutil, subprocess, fnmatch
from pathlib import Path

USAGE = "Usage: package_lambda.py <source_path> <shared_folder> <build_dir> <requirements_file> [comma_separated_excludes]"

# Args
if len(sys.argv) < 5:
    print(USAGE); sys.exit(2)

source_path      = Path(sys.argv[1]).resolve()
shared_folder    = Path(sys.argv[2]).resolve()
build_dir        = Path(sys.argv[3]).resolve()
requirements_file= Path(sys.argv[4]).resolve()
excludes_raw     = sys.argv[5] if len(sys.argv) > 5 else ""
exclude_patterns = [p.strip() for p in excludes_raw.split(",") if p.strip()]

# Safety: build_dir must not be inside source_path
try:
    if source_path in build_dir.parents:
        raise ValueError(f"build_dir {build_dir} must not be inside source_path {source_path}")
except RuntimeError:
    # .parents can raise if paths are on different drives on Windows; ignore
    pass

if not source_path.exists():
    raise FileNotFoundError(f"source_path not found: {source_path}")
if not requirements_file.exists():
    raise FileNotFoundError(f"requirements file not found: {requirements_file}")

def should_exclude(path: Path) -> bool:
    rel = path.name if path.parent == source_path else str(path.relative_to(source_path))
    # always exclude these
    always = {"requirements.txt", "package_lambda.py", ".git", ".terraform", "__pycache__", ".venv", "node_modules", ".build"}
    if path.name in always:
        return True
    for pat in exclude_patterns:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False

# 1. Clean build dir
if build_dir.exists():
    shutil.rmtree(build_dir)
build_dir.mkdir(parents=True, exist_ok=True)

# 2. Install deps into build dir (prefer uv, fallback to pip)
cmd_uv  = ["uv", "pip", "install", "--no-compile", "--target", str(build_dir), "--requirement", str(requirements_file)]
cmd_pip = [sys.executable, "-m", "pip", "install", "--no-compile", "--target", str(build_dir), "--requirement", str(requirements_file)]
try:
    subprocess.run(cmd_uv, check=True)
except FileNotFoundError:
    subprocess.run(cmd_pip, check=True)

# 3. Copy source contents into build (respect excludes)
for item in source_path.iterdir():
    if should_exclude(item):
        continue
    dest = build_dir / item.name
    if item.is_dir():
        # use ignore patterns at top level
        ignore = shutil.ignore_patterns(*exclude_patterns) if exclude_patterns else None
        shutil.copytree(item, dest, dirs_exist_ok=True, ignore=ignore)
    else:
        shutil.copy2(item, dest)

# 4. Copy shared folder into build/shared (if exists)
if shared_folder.exists():
    shutil.copytree(shared_folder, build_dir / "shared", dirs_exist_ok=True)

print(f"Prepared build at: {build_dir}")
