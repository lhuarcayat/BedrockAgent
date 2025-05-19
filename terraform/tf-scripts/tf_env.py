#!/usr/bin/env python3
"""
Unified Terraform helper for ephemeral environments.
Usage examples:
    python tf_env.py switch dev
    python tf_env.py create dev-rolando
    python tf_env.py plan   dev-rolando
    python tf_env.py deploy dev-rolando
    python tf_env.py destroy dev-rolando

if you want to autoapprove or ci/cd purposes you can add the flag -y to autoapprove:
    python tf_env.py deploy -y dev-rolando
    python tf_env.py destroy -y dev-rolando
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE

# ─────────────────────────── Configuration ────────────────────────────
ROOT = Path(__file__).resolve().parents[1]  # .../terraform
LOG   = logging.getLogger("tf-env")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)

# Helper to run shell commands and bubble up failures
def sh(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> str:
    """
    Run *cmd* in *cwd*.
    • When capture=False (default) the command inherits the parent console,
      so you see Terraform’s coloured output live.
    • When capture=True the output is captured and returned (used for
      `terraform output` that you want to save to .env).
    """
    LOG.debug("Running: %s", " ".join(cmd))
    try:
        if capture:
            completed = run(
                cmd,
                cwd=cwd,
                text=True,
                stdout=PIPE,
                stderr=PIPE,
                check=True,
            )
            return completed.stdout
        else:
            run(cmd, cwd=cwd, check=True)      # ↞ streams directly
            return ""
    except CalledProcessError as exc:
        LOG.error("Command failed (exit %s)", exc.returncode)
        sys.exit(exc.returncode)

# ───────────────────────── Terraform wrappers ─────────────────────────
def switch_env(env: str):
    backend_file = ROOT / f"config/{env}.backend.hcl"
    if not backend_file.exists():
        LOG.error("Backend config %s not found", backend_file)
        sys.exit(1)
    sh(["terraform", "init", f"-backend-config={backend_file}", "-reconfigure"], cwd=ROOT)
    LOG.info("Switched to environment %s successfully", env)

def create_env(env: str):
    switch_env("dev")
    sh(["terraform", "workspace", "new", env], cwd=ROOT)
    LOG.info("Created workspace %s", env)

def plan_env(env: str):
    switch_env("dev")
    sh(["terraform", "workspace", "select", env], cwd=ROOT)
    sh([
        "terraform", "plan",
        "-var-file=environments/dev.tfvars",
        f"-var=stage_name={env}"
    ], cwd=ROOT)
    (ROOT / ".env").write_text(sh(["terraform", "output", "-json"], cwd=ROOT, capture=True))
    LOG.info("Plan complete for %s (outputs written to .env)", env)

def deploy_env(env: str, auto_approve: bool = False):
    switch_env("dev")
    sh(["terraform", "workspace", "select", env], cwd=ROOT)
    cmd = ["terraform",
            "apply",
            "-var-file=environments/dev.tfvars",
            f"-var=stage_name={env}"]
    if auto_approve:
        cmd.append("-auto-approve")
    sh(cmd, cwd=ROOT)

    # ---- 1️⃣ capture outputs as JSON  ---------------------------------
    outputs_json = sh(["terraform", "output", "-json"], cwd=ROOT, capture=True)

    # ---- 2️⃣ convert to KEY=val lines (dotenv-friendly) ---------------
    outputs = json.loads(outputs_json)
    lines = [f"{k}={v['value']}" for k, v in outputs.items()]

    # ---- 3️⃣ write to *project-root*/.env exactly like the Bash script
    env_file = ROOT.parent / ".env"
    if not env_file.exists():
        LOG.error(".env file not found at %s – aborting seed", env_file)
        sys.exit(1)
    (env_file).write_text("\n".join(lines) + "\n")

    LOG.info("Deploy succeeded for %s – seeding data", env)
    sh(["node", "seed-restaurants.mjs"], cwd=ROOT.parent)

def destroy_env(env: str, auto_approve: bool = False):
    switch_env("dev")
    sh(["terraform", "workspace", "select", env], cwd=ROOT)
    cmd = ["terraform",
            "destroy",
            "-var-file=environments/dev.tfvars",
            f"-var=stage_name={env}"]
    if auto_approve:
        # Running as a PyInstaller executable
        cmd.append("-auto-approve")
    sh(cmd, cwd=ROOT)
    sh(["terraform", "workspace", "select", "default"], cwd=ROOT)
    sh(["terraform", "workspace", "delete", env], cwd=ROOT)
    LOG.info("Environment %s destroyed and workspace removed", env)

# ────────────────────────────── CLI glue ──────────────────────────────
def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tf_env", description="Terraform env helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    p.add_argument("-y", "--auto-approve",
              action="store_true",
              help="Skip prompts (passes -auto-approve to apply/destroy)")
    for action in ("switch", "create", "plan", "deploy", "destroy"):
        s = sub.add_parser(action)
        s.add_argument("env", help="Environment name (e.g. dev-rolando)")
    return p

def main():
    args = build_cli().parse_args()
    fn = {
        "switch":  switch_env,
        "create":  create_env,
        "plan":    plan_env,
        "deploy":  deploy_env,
        "destroy": destroy_env,
    }[args.cmd]
    if args.cmd in ("deploy", "destroy"):
        fn(args.env, auto_approve=args.auto_approve)
    else:
        fn(args.env)

if __name__ == "__main__":
    main()
