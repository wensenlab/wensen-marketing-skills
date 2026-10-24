#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wensen-marketing-skills 专区自动化备份与多技能同步管理工具
WenSenLab · 文森策 出品

功能概述：
1. 自动比对本地中央技能库 (~/.skills-manager/skills/) 与备份仓库的差异与版本；
2. 智能增量备份：检测文件变动（SHA-256 内容级校验），同步文件并自动维护专区 README.md 索引表格；
3. 全自动 Git 提交与推送：生成语义化 Commit Message 并同步到 GitHub (wensenlab/wensen-marketing-skills)；
4. 统一管理：通过 skills-manifest.json 清单管理专区内多个营销类 skills，支持一键 add/remove/discover；
5. 多模态支持：支持单次同步、--dry-run 预览、--watch 实时监听防抖备份，以及 --install-daemon 后台静默守护。
"""

import os
import sys
import json
import re
import time
import shutil
import hashlib
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# 基础默认路径
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR
DEFAULT_SOURCE_ROOT = Path.home() / ".skills-manager" / "skills"
MANIFEST_PATH = REPO_DIR / "skills-manifest.json"
README_PATH = REPO_DIR / "README.md"
PLIST_LABEL = "com.wensenlab.marketing-skills-sync"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"

# 忽略的文件和目录
IGNORE_NAMES = {
    ".DS_Store", "Thumbs.db", "__pycache__", ".git", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".system", ".system_generated", "node_modules"
}
IGNORE_EXTS = {".pyc", ".pyo", ".pyd", ".swp", ".swo", "~"}


def read_text(path: Path) -> str:
    """读取文本文件"""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    """写入文本文件"""
    path.write_text(content, encoding="utf-8")


def parse_frontmatter(skill_md: Path) -> dict:
    """解析 SKILL.md 中的 YAML Frontmatter"""
    if not skill_md.is_file():
        return {}
    content = read_text(skill_md)
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}
    
    yaml_block = match.group(1)
    data = {}
    
    # 基础轻量解析
    current_key = None
    multiline_buf = []
    
    for line in yaml_block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            if current_key and multiline_buf:
                data[current_key] = "\n".join(multiline_buf).strip().strip('"').strip("'")
                multiline_buf = []
            key, val = line.split(":", 1)
            current_key = key.strip()
            val_clean = val.strip()
            if val_clean in (">", ">-", "|", "|-"):
                multiline_buf = []
            elif val_clean:
                data[current_key] = val_clean.strip('"').strip("'")
            else:
                multiline_buf = []
        elif current_key and (line.startswith("  ") or line.startswith("\t")):
            multiline_buf.append(line.strip())
            
    if current_key and multiline_buf:
        data[current_key] = " ".join(multiline_buf).strip().strip('"').strip("'")
        
    return data


def compute_file_hash(path: Path) -> str:
    """计算单个文件的 SHA-256 哈希值"""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_skill_signature(skill_dir: Path) -> dict[str, str]:
    """计算技能目录下所有有效文件的相对路径与哈希签名"""
    signatures = {}
    if not skill_dir.is_dir():
        return signatures
    
    for root, dirs, files in os.walk(skill_dir):
        # 排除忽略目录
        dirs[:] = [d for d in dirs if d not in IGNORE_NAMES and not d.startswith(".")]
        for file in files:
            if file in IGNORE_NAMES or file.startswith(".") or any(file.endswith(ext) for ext in IGNORE_EXTS):
                continue
            file_path = Path(root) / file
            rel_path = file_path.relative_to(skill_dir).as_posix()
            signatures[rel_path] = compute_file_hash(file_path)
            
    return signatures


def load_manifest() -> dict:
    """加载纳管清单 skills-manifest.json"""
    if MANIFEST_PATH.is_file():
        try:
            return json.loads(read_text(MANIFEST_PATH))
        except Exception as e:
            print(f"[警告] 读取 manifest 失败: {e}，将使用初始模板")
            
    # 默认初始配置
    default_manifest = {
        "version": "1.0.0",
        "repo": "wensenlab/wensen-marketing-skills",
        "source_root": str(DEFAULT_SOURCE_ROOT),
        "updated_at": datetime.now().isoformat(),
        "skills": [
            {
                "name": "brand-strategy-analyst",
                "category": "品牌策略",
                "status": "active",
                "added_at": datetime.now().strftime("%Y-%m-%d")
            }
        ]
    }
    save_manifest(default_manifest)
    return default_manifest


def save_manifest(manifest: dict) -> None:
    """保存纳管清单"""
    manifest["updated_at"] = datetime.now().isoformat()
    write_text(MANIFEST_PATH, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def get_source_root(manifest: dict) -> Path:
    """解析本地技能源目录"""
    raw_path = manifest.get("source_root", str(DEFAULT_SOURCE_ROOT))
    expanded = Path(os.path.expanduser(raw_path)).resolve()
    return expanded


def sync_skill_directory(src_dir: Path, dest_dir: Path, dry_run: bool = False) -> tuple[int, int, int]:
    """
    镜像同步单个技能目录：
    返回 (新增/修改文件数, 删除文件数, 保持不变数)
    """
    src_sigs = compute_skill_signature(src_dir)
    dest_sigs = compute_skill_signature(dest_dir)
    
    modified_count = 0
    deleted_count = 0
    unchanged_count = 0
    
    # 1. 复制新增或修改的文件
    for rel_path, src_hash in src_sigs.items():
        src_file = src_dir / rel_path
        dest_file = dest_dir / rel_path
        
        if rel_path not in dest_sigs or dest_sigs[rel_path] != src_hash:
            modified_count += 1
            if not dry_run:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
        else:
            unchanged_count += 1
            
    # 2. 删除目标目录中多余的文件（本地已删除的文件）
    for rel_path in dest_sigs:
        if rel_path not in src_sigs:
            deleted_count += 1
            if not dry_run:
                dest_file = dest_dir / rel_path
                dest_file.unlink(missing_ok=True)
                
    # 3. 清理目标目录中的空文件夹
    if not dry_run and dest_dir.is_dir():
        for root, dirs, files in os.walk(dest_dir, topdown=False):
            for d in dirs:
                dir_path = Path(root) / d
                try:
                    dir_path.rmdir()
                except OSError:
                    pass
                    
    return modified_count, deleted_count, unchanged_count


def update_readme_matrix(skills_meta: list[dict], dry_run: bool = False) -> bool:
    """
    动态更新 README.md 中的技能矩阵表格
    """
    if not README_PATH.is_file():
        return False
        
    content = read_text(README_PATH)
    
    # 生成 Markdown 表格
    lines = [
        "| 技能目录 | 技能定位与核心价值 | 适用场景与触发词 | 版本 | 状态 |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for s in skills_meta:
        name = s["name"]
        version = s.get("version", "v1.0.0")
        desc = s.get("description", "品牌营销策略技能")
        category = s.get("category", "营销策略")
        
        # 简化描述供表格排版（取前 120 字）
        short_desc = desc.replace("\n", " ").strip()
        if len(short_desc) > 130:
            short_desc = short_desc[:127] + "..."
            
        link = f"[`skills/{name}`](skills/{name}/)"
        line = f"| {link} | **{category}**<br/>{short_desc} | 详见技能定义说明 | `{version}` | ✅ 已就绪 |"
        lines.append(line)
        
    new_table = "\n".join(lines)
    
    # 正则替换表格区域
    pattern = r"(## 📂 专区技能矩阵清单 \(Skills Matrix\)\s*\n\s*\n)(.*?)(?=\n---\n|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        header = match.group(1)
        updated_content = content[:match.start()] + header + new_table + "\n" + content[match.end():]
    else:
        # 如果未找到区域，直接插入到合适位置
        updated_content = content + "\n\n## 📂 专区技能矩阵清单 (Skills Matrix)\n\n" + new_table + "\n"
        
    if updated_content != content:
        if not dry_run:
            write_text(README_PATH, updated_content)
        return True
    return False


def git_commit_and_push(changed_skills: list[str], dry_run: bool = False) -> bool:
    """执行 Git add, commit 与 push"""
    if dry_run:
        print("[Dry-Run] 预览模式，跳过 Git 提交与推送")
        return True
        
    try:
        # 1. git add
        subprocess.run(["git", "add", "skills/", "skills-manifest.json", "README.md", "sync_marketing_skills.py"], cwd=REPO_DIR, check=True)
        
        # 2. 检查是否有暂存的更改
        res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR)
        if res.returncode == 0:
            print("[Git] 无暂存更改，无需提交。")
            return True
            
        # 3. 构造语义化 Commit Message
        if len(changed_skills) == 1:
            commit_msg = f"sync({changed_skills[0]}): 自动同步技能最新版本与改动"
        elif len(changed_skills) > 1:
            joined = ", ".join(changed_skills[:3])
            if len(changed_skills) > 3:
                joined += f" 等 {len(changed_skills)} 个技能"
            commit_msg = f"sync(skills): 批量同步 {joined} 最新版本"
        else:
            commit_msg = "sync(manifest): 更新专区技能清单与索引"
            
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
        print(f"[Git] 成功提交: {commit_msg}")
        
        # 4. git push
        print("[Git] 正在推送到 GitHub 远程仓库 (origin/main)...")
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        print("[Git] ✓ 成功推送至 GitHub！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Git 错误] 执行异常: {e}")
        return False


def run_sync(target_skill: str = None, dry_run: bool = False) -> bool:
    """执行同步主流程"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    skills_list = manifest.get("skills", [])
    
    if not source_root.is_dir():
        print(f"[错误] 本地技能权威源路径不存在: {source_root}")
        return False
        
    print(f"=== WenSenLab 营销技能专区同步巡检 ===")
    print(f"本地权威源: {source_root}")
    print(f"备份仓库:   {REPO_DIR}")
    print(f"纳管技能数: {len(skills_list)}\n")
    
    changed_skills = []
    skills_meta = []
    
    for item in skills_list:
        name = item["name"]
        if target_skill and name != target_skill:
            continue
            
        src_skill_dir = source_root / name
        dest_skill_dir = REPO_DIR / "skills" / name
        
        if not src_skill_dir.is_dir():
            print(f"[-] [缺失] 本地未找到技能目录: {src_skill_dir}")
            continue
            
        # 解析元数据
        fm = parse_frontmatter(src_skill_dir / "SKILL.md")
        version = fm.get("metadata", {}).get("version") if isinstance(fm.get("metadata"), dict) else fm.get("version", "v1.0.0")
        desc = fm.get("description", item.get("category", "营销策略分析"))
        
        meta = {
            "name": name,
            "version": version,
            "description": desc,
            "category": item.get("category", "营销策略")
        }
        skills_meta.append(meta)
        
        # 执行文件比对与同步
        mod_count, del_count, same_count = sync_skill_directory(src_skill_dir, dest_skill_dir, dry_run=dry_run)
        
        if mod_count > 0 or del_count > 0:
            changed_skills.append(name)
            prefix = "[Dry-Run 变动]" if dry_run else "[同步更新]"
            print(f"[*] {prefix} {name} ({version}): 新增/修改 {mod_count} 个文件，删除 {del_count} 个文件")
        else:
            print(f"[✓] [保持最新] {name} ({version}): {same_count} 个文件完全一致")
            
    # 刷新 README 表格
    readme_updated = update_readme_matrix(skills_meta, dry_run=dry_run)
    if readme_updated:
        print("[✓] README.md 专区技能索引表格已同步更新")
        
    # 保存 manifest
    if changed_skills and not dry_run:
        save_manifest(manifest)
        
    # Git 提交与推送
    if changed_skills or readme_updated:
        print(f"\n检测到 {len(changed_skills)} 个技能变动，准备提交备份...")
        return git_commit_and_push(changed_skills, dry_run=dry_run)
    else:
        print("\n[OK] 所有营销技能均已是最新状态，无需重复推送。")
        return True


def run_status():
    """查看当前专区纳管技能状态"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    skills_list = manifest.get("skills", [])
    
    print(f"=== wensen-marketing-skills 专区纳管清单 ({len(skills_list)} 个技能) ===\n")
    print(f"{'技能名称':<28} | {'版本':<8} | {'类别':<10} | {'同步状态'}")
    print("-" * 75)
    
    for item in skills_list:
        name = item["name"]
        category = item.get("category", "通用")
        src_dir = source_root / name
        dest_dir = REPO_DIR / "skills" / name
        
        if not src_dir.is_dir():
            status = "❌ 本地权威源缺失"
            ver = "-"
        elif not dest_dir.is_dir():
            status = "⚠️  尚未备份到仓库"
            fm = parse_frontmatter(src_dir / "SKILL.md")
            ver = fm.get("version", "v1.0.0")
        else:
            src_sig = compute_skill_signature(src_dir)
            dest_sig = compute_skill_signature(dest_dir)
            fm = parse_frontmatter(src_dir / "SKILL.md")
            ver = fm.get("version", "v1.0.0")
            if src_sig == dest_sig:
                status = "✓ 已同步最新"
            else:
                status = "🔄 本地存在未提交更新"
                
        print(f"{name:<28} | {ver:<8} | {category:<10} | {status}")


def cmd_add_skill(skill_name: str, category: str = "营销策略"):
    """将本地某个 skill 加入本专区纳管清单并执行同步"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    src_dir = source_root / skill_name
    
    if not src_dir.is_dir():
        print(f"[错误] 在本地权威源 {source_root} 下未找到技能 '{skill_name}'")
        sys.exit(1)
        
    # 检查是否已在清单中
    existing = [s for s in manifest.get("skills", []) if s["name"] == skill_name]
    if existing:
        print(f"[提示] 技能 '{skill_name}' 已在纳管清单中，无需重复添加。")
    else:
        manifest["skills"].append({
            "name": skill_name,
            "category": category,
            "status": "active",
            "added_at": datetime.now().strftime("%Y-%m-%d")
        })
        save_manifest(manifest)
        print(f"[成功] 技能 '{skill_name}' 已添加至营销技能清单。")
        
    # 立即执行一次同步
    run_sync(target_skill=skill_name)


def cmd_remove_skill(skill_name: str):
    """从专区清单中移除某个 skill"""
    manifest = load_manifest()
    skills = manifest.get("skills", [])
    new_skills = [s for s in skills if s["name"] != skill_name]
    
    if len(new_skills) == len(skills):
        print(f"[提示] 技能 '{skill_name}' 不在清单中。")
        return
        
    manifest["skills"] = new_skills
    save_manifest(manifest)
    print(f"[成功] 技能 '{skill_name}' 已从清单中移除。")
    print(f"[提示] 仓库中已备份的 skills/{skill_name}/ 目录已保留，如需彻底删除可手动执行 git rm。")


def cmd_discover():
    """自动扫描本地所有可能属于营销/策略类的技能"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    managed_names = {s["name"] for s in manifest.get("skills", [])}
    
    print(f"=== 扫描本地营销与商业策略候选技能 ({source_root}) ===\n")
    candidates = []
    
    for child in sorted(source_root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name in IGNORE_NAMES:
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
            
        fm = parse_frontmatter(skill_md)
        name = fm.get("name", child.name)
        desc = fm.get("description", "")
        
        # 关键词匹配
        kw_pattern = r"(营销|策略|品牌|比稿|广告|文案|自媒体|策划|商业|定位|传播|marketing|brand|strategy|copywriting)"
        is_candidate = re.search(kw_pattern, name, re.IGNORECASE) or re.search(kw_pattern, desc, re.IGNORECASE)
        
        if is_candidate:
            status = "✅ 已纳管" if name in managed_names else "💡 可纳管"
            candidates.append((name, status, desc[:80] + "..."))
            
    for name, status, snippet in candidates:
        print(f"{status} | {name:<26} | {snippet}")
        
    print("\n提示：若需纳管候选技能，可执行：")
    print("  python3 sync_marketing_skills.py add <技能名称>")


def run_watch(interval: int = 5):
    """文件变更监听守护模式（轮询 + SHA 防抖）"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    skills = [s["name"] for s in manifest.get("skills", [])]
    
    print(f"=== 启动营销技能实时监听守护模式 (防抖间隔: {interval}s) ===")
    print(f"正在监听的技能: {', '.join(skills)}")
    print("按 Ctrl+C 可退出监听。\n")
    
    last_snapshots = {}
    for name in skills:
        src_dir = source_root / name
        if src_dir.is_dir():
            last_snapshots[name] = compute_skill_signature(src_dir)
            
    while True:
        try:
            time.sleep(interval)
            changed = []
            for name in skills:
                src_dir = source_root / name
                if not src_dir.is_dir():
                    continue
                current_sig = compute_skill_signature(src_dir)
                if current_sig != last_snapshots.get(name):
                    changed.append(name)
                    last_snapshots[name] = current_sig
                    
            if changed:
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{now_str}] 检测到技能文件变动: {', '.join(changed)}，触发自动备份...")
                run_sync()
        except KeyboardInterrupt:
            print("\n[退出] 实时监听守护已停止。")
            break


def cmd_install_daemon():
    """安装 macOS LaunchAgent 后台静默守护定时任务"""
    python_bin = sys.executable
    script_path = str(Path(__file__).resolve())
    log_path = Path.home() / "Library" / "Logs" / "wensen_marketing_skills_sync.log"
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{script_path}</string>
        <string>sync</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_text(PLIST_PATH, plist_content)
    
    try:
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
        print(f"[成功] macOS 后台守护已安装并激活！")
        print(f"• 触发频率: 每 30 分钟静默增量巡检一次")
        print(f"• 运行日志: {log_path}")
        print(f"• 卸载命令: python3 {Path(__file__).name} --uninstall-daemon")
    except Exception as e:
        print(f"[错误] 激活 LaunchAgent 失败: {e}")


def cmd_uninstall_daemon():
    """卸载 macOS LaunchAgent 后台守护"""
    if PLIST_PATH.is_file():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink(missing_ok=True)
        print(f"[成功] macOS 后台守护任务已卸载并清理。")
    else:
        print(f"[提示] 未找到已安装的后台守护任务。")


def main():
    parser = argparse.ArgumentParser(
        description="WenSenLab · 营销与商业策略技能自动化备份与统一管理中枢",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用示例:
  python3 sync_marketing_skills.py                     # 执行全量增量检查与备份同步
  python3 sync_marketing_skills.py status              # 查看专区纳管技能及同步状态
  python3 sync_marketing_skills.py add marketing-council  # 新增一个营销类技能并立即同步
  python3 sync_marketing_skills.py discover            # 自动发现本地候选营销类技能
  python3 sync_marketing_skills.py --watch             # 开启终端前台实时监听（保存即自动备份）
  python3 sync_marketing_skills.py --install-daemon    # 一键注册 macOS 后台守护（每 30 分钟无感巡检）
        """
    )
    
    # 选项
    parser.add_argument("--dry-run", action="store_true", help="预览变动，不实际修改文件或提交 Git")
    parser.add_argument("--watch", action="store_true", help="启动前台实时监听模式，文件改动防抖后自动备份")
    parser.add_argument("--install-daemon", action="store_true", help="注册 macOS LaunchAgent 后台每 30 分钟自动备份")
    parser.add_argument("--uninstall-daemon", action="store_true", help="卸载 macOS LaunchAgent 后台任务")
    
    # 子命令
    subparsers = parser.add_subparsers(dest="subcommand", help="支持的子命令")
    
    # sync
    p_sync = subparsers.add_parser("sync", help="执行同步 (默认动作)")
    p_sync.add_argument("--skill", "-s", help="只同步指定名称的技能")
    
    # status
    subparsers.add_parser("status", help="查看所有纳管技能的同步状态")
    
    # add
    p_add = subparsers.add_parser("add", help="将本地新技能添加至营销专区清单")
    p_add.add_argument("name", help="技能名称 (对应 ~/.skills-manager/skills/ 下的目录名)")
    p_add.add_argument("--category", "-c", default="营销策略", help="分类标签 (默认: 营销策略)")
    
    # remove
    p_rm = subparsers.add_parser("remove", help="从专区清单中移除技能")
    p_rm.add_argument("name", help="技能名称")
    
    # discover
    subparsers.add_parser("discover", help="扫描本地所有可能属于营销类的技能")
    
    args = parser.parse_args()
    
    # 优先处理高级控制选项
    if args.install_daemon:
        cmd_install_daemon()
        return
    if args.uninstall_daemon:
        cmd_uninstall_daemon()
        return
    if args.watch:
        run_watch()
        return
        
    # 分流子命令
    if args.subcommand == "status":
        run_status()
    elif args.subcommand == "add":
        cmd_add_skill(args.name, args.category)
    elif args.subcommand == "remove":
        cmd_remove_skill(args.name)
    elif args.subcommand == "discover":
        cmd_discover()
    else:
        # 默认执行 sync
        target = getattr(args, "skill", None)
        run_sync(target_skill=target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
