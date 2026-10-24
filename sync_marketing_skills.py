#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wensen-marketing-skills 专区自动化备份与多技能同步管理工具
WenSenLab · 文森策 出品

核心特性：
1. 采用 macOS 原生 LaunchAgent + WatchPaths 机制，本地文件一旦保存修改，系统底层秒级自动触发备份与推送；
2. 无常驻后台进程，非修改期间 CPU 0%、内存 0MB，轻量无感；
3. SHA-256 内容级指纹比对，自动过滤 .DS_Store 等临时垃圾，无实质修改绝不产生冗余提交；
4. 自动解析提取 Frontmatter 版本与元数据，动态生成语义化 Commit Message 并同步维护专区 README 索引矩阵；
5. 支持 skills-manifest.json 统一管理，支持一键 add/remove/discover 扩充新营销技能。
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

# 补全 PATH 环境变量确保 Git 等命令在 launchd 各种环境下均可执行
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")

# 基础默认路径
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR
DEFAULT_SOURCE_ROOT = Path.home() / ".skills-manager" / "skills"
MANIFEST_PATH = REPO_DIR / "skills-manifest.json"
README_PATH = REPO_DIR / "README.md"

# 统一遵循 ~/Library/LaunchAgents/ 下 com.wensenlab.* 命名体系
PLIST_LABEL = "com.wensenlab.marketing-skills.backup"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
STDOUT_LOG = Path("/tmp/com.wensenlab.marketing-skills.backup.out")
STDERR_LOG = Path("/tmp/com.wensenlab.marketing-skills.backup.err")

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
    """镜像同步单个技能目录：返回 (新增/修改数, 删除数, 保持不变数)"""
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
            
    # 2. 删除目标目录中多余的文件
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
    """动态更新 README.md 中的技能矩阵表格"""
    if not README_PATH.is_file():
        return False
        
    content = read_text(README_PATH)
    lines = [
        "| 技能目录 | 技能定位与核心价值 | 适用场景与触发词 | 版本 | 状态 |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for s in skills_meta:
        name = s["name"]
        version = s.get("version", "v1.0.0")
        desc = s.get("description", "品牌营销策略技能")
        category = s.get("category", "营销策略")
        
        short_desc = desc.replace("\n", " ").strip()
        if len(short_desc) > 130:
            short_desc = short_desc[:127] + "..."
            
        link = f"[`skills/{name}`](skills/{name}/)"
        line = f"| {link} | **{category}**<br/>{short_desc} | 详见技能定义说明 | `{version}` | ✅ 已就绪 |"
        lines.append(line)
        
    new_table = "\n".join(lines)
    pattern = r"(## 📂 专区技能矩阵清单 \(Skills Matrix\)\s*\n\s*\n)(.*?)(?=\n---\n|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        header = match.group(1)
        updated_content = content[:match.start()] + header + new_table + "\n" + content[match.end():]
    else:
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
        subprocess.run(["git", "add", "skills/", "skills-manifest.json", "README.md", "sync_marketing_skills.py"], cwd=REPO_DIR, check=True)
        res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR)
        if res.returncode == 0:
            print("[Git] 无暂存更改，无需提交。")
            return True
            
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if len(changed_skills) == 1:
            commit_msg = f"Auto-backup: 同步 {changed_skills[0]} 最新改动 ({now_time})"
        elif len(changed_skills) > 1:
            joined = ", ".join(changed_skills[:3])
            if len(changed_skills) > 3:
                joined += f" 等 {len(changed_skills)} 个技能"
            commit_msg = f"Auto-backup: 批量同步 {joined} ({now_time})"
        else:
            commit_msg = f"Auto-backup: 更新专区清单与索引 ({now_time})"
            
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
        print(f"[Git] 成功提交: {commit_msg}")
        
        print("[Git] 正在推送到 GitHub 远程仓库 (origin/main)...")
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        print("[Git] ✓ 成功推送至 GitHub！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Git 错误] 执行异常: {e}")
        return False


def get_all_watch_paths(manifest: dict) -> list[str]:
    """生成所有纳管技能的精确监控路径列表"""
    source_root = get_source_root(manifest)
    paths = []
    
    for item in manifest.get("skills", []):
        name = item["name"]
        skill_dir = source_root / name
        if skill_dir.is_dir():
            paths.append(str(skill_dir))
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                paths.append(str(skill_md))
            for sub in ["references", "evals", "scripts", "assets"]:
                subdir = skill_dir / sub
                if subdir.is_dir():
                    paths.append(str(subdir))
                    
    # 额外监控清单本身
    paths.append(str(MANIFEST_PATH))
    return sorted(list(set(paths)))


def ensure_launch_agent(manifest: dict = None, force_reload: bool = False) -> bool:
    """
    自动对齐并安装 macOS LaunchAgent 自动化守护：
    基于原生 WatchPaths 监听，本地文件保存后秒级触发，零常驻进程，零 CPU 占用。
    """
    if manifest is None:
        manifest = load_manifest()
        
    watch_paths = get_all_watch_paths(manifest)
    watch_xml = "\n".join([f"        <string>{p}</string>" for p in watch_paths])
    python_bin = "/usr/bin/python3"
    script_path = str(REPO_DIR / "sync_marketing_skills.py")
    
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
    <key>WatchPaths</key>
    <array>
{watch_xml}
    </array>
    <key>ThrottleInterval</key>
    <integer>3</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{STDOUT_LOG}</string>
    <key>StandardErrorPath</key>
    <string>{STDERR_LOG}</string>
</dict>
</plist>
"""
    # 检查是否已有配置且内容一致
    is_updated = False
    if PLIST_PATH.is_file():
        old_content = read_text(PLIST_PATH)
        if old_content.strip() != plist_content.strip():
            is_updated = True
    else:
        is_updated = True
        
    if is_updated or force_reload:
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_text(PLIST_PATH, plist_content)
        try:
            subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
            subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
            print(f"[LaunchAgent] ✓ 自动化守护已就绪 (监控 {len(watch_paths)} 处路径)")
            return True
        except Exception as e:
            print(f"[LaunchAgent 警告] 激活失败: {e}")
            return False
            
    return True


def run_sync(target_skill: str = None, dry_run: bool = False, delay: int = 2) -> bool:
    """执行同步主流程"""
    if delay > 0 and not dry_run:
        time.sleep(delay)
        
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    skills_list = manifest.get("skills", [])
    
    if not source_root.is_dir():
        print(f"[错误] 本地技能权威源路径不存在: {source_root}")
        return False
        
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === WenSenLab 营销技能专区自动同步巡检 ===")
    
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
        
        mod_count, del_count, same_count = sync_skill_directory(src_skill_dir, dest_skill_dir, dry_run=dry_run)
        
        if mod_count > 0 or del_count > 0:
            changed_skills.append(name)
            prefix = "[Dry-Run 变动]" if dry_run else "[同步更新]"
            print(f"[*] {prefix} {name} ({version}): 新增/修改 {mod_count} 个文件，删除 {del_count} 个文件")
        else:
            print(f"[✓] [保持最新] {name} ({version}): {same_count} 个文件完全一致")
            
    readme_updated = update_readme_matrix(skills_meta, dry_run=dry_run)
    if readme_updated:
        print("[✓] README.md 专区技能索引表格已同步更新")
        
    if changed_skills and not dry_run:
        save_manifest(manifest)
        
    # 确保 LaunchAgent 监控路径与 manifest 保持最新
    if not dry_run:
        ensure_launch_agent(manifest)
        
    if changed_skills or readme_updated:
        print(f"检测到 {len(changed_skills)} 个技能变动，正在提交 GitHub 备份...")
        return git_commit_and_push(changed_skills, dry_run=dry_run)
    else:
        print("[OK] 所有营销技能均已是最新状态，无需重复推送。")
        return True


def run_status():
    """查看当前专区纳管技能状态与自动化守护运行状况"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    skills_list = manifest.get("skills", [])
    
    agent_status = "未激活"
    if PLIST_PATH.is_file():
        res = subprocess.run(["launchctl", "list", PLIST_LABEL], capture_output=True, text=True)
        if res.returncode == 0:
            agent_status = "🟢 正在后台监听 (自动同步已就绪)"
        else:
            agent_status = "🟡 配置文件存在但未加载"
    else:
        agent_status = "🔴 未安装"
        
    print(f"=== wensen-marketing-skills 专区纳管状态 ===")
    print(f"自动化守护: {agent_status}")
    print(f"监控配置文件: {PLIST_PATH}")
    print(f"日志输出位置: {STDOUT_LOG}\n")
    print(f"{'技能名称':<28} | {'版本':<8} | {'类别':<10} | {'本地/线上对齐状态'}")
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
                status = "🔄 本地存在未提交改动"
                
        print(f"{name:<28} | {ver:<8} | {category:<10} | {status}")


def cmd_add_skill(skill_name: str, category: str = "营销策略"):
    """将本地某个 skill 加入本专区纳管清单，自动更新 LaunchAgent 监控并同步"""
    manifest = load_manifest()
    source_root = get_source_root(manifest)
    src_dir = source_root / skill_name
    
    if not src_dir.is_dir():
        print(f"[错误] 在本地权威源 {source_root} 下未找到技能 '{skill_name}'")
        sys.exit(1)
        
    existing = [s for s in manifest.get("skills", []) if s["name"] == skill_name]
    if existing:
        print(f"[提示] 技能 '{skill_name}' 已在纳管清单中。")
    else:
        manifest["skills"].append({
            "name": skill_name,
            "category": category,
            "status": "active",
            "added_at": datetime.now().strftime("%Y-%m-%d")
        })
        save_manifest(manifest)
        print(f"[成功] 技能 '{skill_name}' 已添加至营销专区清单。")
        
    ensure_launch_agent(manifest, force_reload=True)
    run_sync(target_skill=skill_name, delay=0)


def cmd_remove_skill(skill_name: str):
    """从专区清单中移除某个 skill 并刷新监控配置"""
    manifest = load_manifest()
    skills = manifest.get("skills", [])
    new_skills = [s for s in skills if s["name"] != skill_name]
    
    if len(new_skills) == len(skills):
        print(f"[提示] 技能 '{skill_name}' 不在清单中。")
        return
        
    manifest["skills"] = new_skills
    save_manifest(manifest)
    ensure_launch_agent(manifest, force_reload=True)
    print(f"[成功] 技能 '{skill_name}' 已从清单中移除，监控已刷新。")


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
        
        kw_pattern = r"(营销|策略|品牌|比稿|广告|文案|自媒体|策划|商业|定位|传播|marketing|brand|strategy|copywriting)"
        is_candidate = re.search(kw_pattern, name, re.IGNORECASE) or re.search(kw_pattern, desc, re.IGNORECASE)
        
        if is_candidate:
            status = "✅ 已纳管" if name in managed_names else "💡 可纳管"
            candidates.append((name, status, desc[:80] + "..."))
            
    for name, status, snippet in candidates:
        print(f"{status} | {name:<26} | {snippet}")
        
    print("\n提示：若需纳管候选技能，可执行：")
    print("  python3 sync_marketing_skills.py add <技能名称>")


def main():
    parser = argparse.ArgumentParser(
        description="WenSenLab · 营销与商业策略技能自动化备份与统一管理中枢",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--dry-run", action="store_true", help="预览变动，不实际修改文件或提交 Git")
    parser.add_argument("--setup-daemon", action="store_true", help="强制重新安装/激活 macOS LaunchAgent 自动化守护")
    
    subparsers = parser.add_subparsers(dest="subcommand", help="支持的子命令")
    
    p_sync = subparsers.add_parser("sync", help="执行同步 (默认动作)")
    p_sync.add_argument("--skill", "-s", help="只同步指定名称的技能")
    
    subparsers.add_parser("status", help="查看所有纳管技能的同步状态与自动化守护情况")
    
    p_add = subparsers.add_parser("add", help="将本地新技能添加至营销专区清单")
    p_add.add_argument("name", help="技能名称 (对应 ~/.skills-manager/skills/ 下的目录名)")
    p_add.add_argument("--category", "-c", default="营销策略", help="分类标签 (默认: 营销策略)")
    
    p_rm = subparsers.add_parser("remove", help="从专区清单中移除技能")
    p_rm.add_argument("name", help="技能名称")
    
    subparsers.add_parser("discover", help="扫描本地所有可能属于营销类的技能")
    
    args = parser.parse_args()
    
    if args.setup_daemon:
        ensure_launch_agent(force_reload=True)
        return
        
    if args.subcommand == "status":
        run_status()
    elif args.subcommand == "add":
        cmd_add_skill(args.name, args.category)
    elif args.subcommand == "remove":
        cmd_remove_skill(args.name)
    elif args.subcommand == "discover":
        cmd_discover()
    else:
        target = getattr(args, "skill", None)
        run_sync(target_skill=target, dry_run=args.dry_run, delay=0)


if __name__ == "__main__":
    main()
