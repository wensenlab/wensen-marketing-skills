# 🎯 wensen-marketing-skills — WenSenLab 品牌商业策略与营销策划 Agent Skills 专区

> **WenSenLab_ ©文森策 出品**
> 
> 本仓库是 WenSenLab 旗下面向品牌商业策略、整合营销策划与商业洞察的工业级 Agent Skills 专属资产库。
> 融合文森策十余年 4A 整合营销与品牌战略咨询的实战内功，摆脱传统大模型“泛泛而谈、全是大厂黑话和正确废话”的通病，输出真正具备落地商业价值、能直接放进提案 PPT 的高品质策略方案。

---

## 📂 专区技能矩阵清单 (Skills Matrix)

| 技能目录 | 技能定位与核心价值 | 适用场景与触发词 | 版本 | 状态 |
| :--- | :--- | :--- | :--- | :--- |
| [`skills/brand-strategy-analyst`](skills/brand-strategy-analyst/) | **品牌策略**<br/>资深品牌策略分析师与商业洞察中枢（Senior Brand Strategy Analyst），由 WenSenLab · 文森策打造。当用户提到以下需求时必须主动触发：品牌定位分析、商业策略推演、竞品差异化诊断、品牌资产梳理、撰写比稿策略大纲、推导 B... | 详见技能定义说明 | `v1.0.0` | ✅ 已就绪 |

---

## 🌟 核心设计哲学与规范约束

1. **商业破局始于市场张力 (Tension First)**：拒绝流于表面的 SWOT 罗列。真正的战略破局点，永远藏在“行业默认的共识惯性”与“消费者深层未被满足的矛盾”之间的拉扯中。
2. **直切人群心智切片 (Deep Persona)**：彻底终结“25-35 岁一二线都市中产”这类无效标签，穿透至微观生活场景、社交防御机制、心理阻力与真实买单账户。
3. **语言去班味，客观求真 (Human-Writing)**：严密过滤“赋能、闭环、抓手、心智占领”等空洞大厂套话，用通俗精准的商业人话讲透因果逻辑。
4. **平等松弛，拒绝爹味 (No Preaching)**：绝不以居高临下的导师口吻教读者做事，杜绝命令式训导，以第一人称实战与同行交流的平视视角输出建议。
5. **标点与排版对齐**：中文语境下严格对齐全角中文标点，保持 1～2 句微段落呼吸感。

---

## 🚀 安装与部署方式 (Deployment)

### 方式 1：通过 Skills Manager 一键纳管与同步（推荐）

本技能原生支持 `skills-manager-cli`：

```bash
# 从 GitHub 仓库一键安装至本地中央技能库
skills-manager-cli skills install https://github.com/wensenlab/wensen-marketing-skills.git --subpath skills/brand-strategy-analyst

# 部署至指定 Agent 环境（如 Antigravity, Claude Code, Codex, WorkBuddy）
skills-manager-cli skills deploy --agent antigravity brand-strategy-analyst
skills-manager-cli skills deploy --agent claude_code brand-strategy-analyst
```

### 方式 2：手动本地挂载

直接将技能目录克隆或软链接至各 Agent 的 skills 路径：

```bash
# 示例：软链接至本地 Agent 目录
ln -s "/path/to/wensen-marketing-skills/skills/brand-strategy-analyst" ~/.agents/skills/brand-strategy-analyst
```

---

## 📁 专区目录结构规范

```
wensen-marketing-skills/
├── README.md                              # 专区导航与使用指南
└── skills/
    └── brand-strategy-analyst/            # 品牌策略分析师技能
        ├── SKILL.md                       # 核心推演工作流与标杆示例
        ├── evals/
        │   └── evals.json                 # 工业级比稿测试集
        └── references/
            ├── category-tension-matrix.md # 行业张力与商业破局推演指南
            ├── deep-persona-guide.md      # 深度人群画像心智切片指南
            └── negative-dictionary.md     # 策略黑话过滤与正向替换词典
```

---

## 📄 版权与厂牌规范

本项目所有技能资产归属于试验工坊厂牌 **WenSenLab**。  
**WenSenLab_ ©文森策** 版权所有。
