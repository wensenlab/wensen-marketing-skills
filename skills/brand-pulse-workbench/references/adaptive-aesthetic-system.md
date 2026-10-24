# 自适应品牌美学调色盘与视觉系统 (Adaptive Brand Aesthetic System)

本规范为 `brand-pulse-workbench` 在编译单文件交互看板时，提供权威的品牌性格与前端视觉映射指南。
Agent 必须根据输入的品牌调性与核心行业属性，自动适配以下 5 大美学预设之一，杜绝“千篇一律的通用模板感”。

---

## 1. 五大核心品牌性格视觉预设

### 预设 A：科技极客与未来工业 (Tech & Geek)
- **典型品牌**：Apple、Tesla、大疆 (DJI)、Nothing、Sony
- **视觉气质**：克制、冷峻、高精密、极客理性
- **配色规范 (Tailwind Classes & Hex)**：
  - 背景底色：`bg-[#0A0D14]`（深邃暗夜）或 `bg-[#F5F6F8]`（冷白工作台）
  - 容器卡片：`bg-[#121722]/80 backdrop-blur-md border border-[#232B3E]`（暗色态）或 `bg-white/90 border border-slate-200`（明亮态）
  - 核心主色：`text-cyan-400` / `bg-cyan-500` 或 `text-indigo-400` / `bg-indigo-600`
  - 辅助强调：`text-blue-500`、`border-cyan-500/30`
  - 文字层级：标题 `text-slate-100 font-semibold tracking-tight`，正文 `text-slate-400 font-mono text-sm`
- **设计细节**：
  - 细边框（`border border-slate-700/50`）、微磨砂亚克力玻璃（`backdrop-blur`）；
  - 数据与标签带等宽字体韵律（`font-mono`）；
  - 图标与指示线采用高精度细线（Stroke 1.5）。

---

### 预设 B：人文知性与生活美学 (Humanistic & Lifestyle)
- **典型品牌**：Volvo、Aesop、观夏 (To Summer)、MUJI、安缦 (Aman)
- **视觉气质**：松弛、温润、呼吸感、当代东方与北欧质感交融
- **配色规范 (Tailwind Classes & Hex)**：
  - 背景底色：`bg-[#F8F6F0]`（大地暖白/亚麻纸质感）
  - 容器卡片：`bg-[#FFFFFF] border border-[#E9E4D9] shadow-sm`
  - 核心主色：`text-[#2C2926]`（石墨黛黑）与 `text-[#5C5549]`（风化茶褐）
  - 辅助强调：`text-[#6B7D72]` / `bg-[#6B7D72]`（松石灰绿）、`bg-[#D4A373]/20`（暖陶土）
  - 文字层级：主标题 `font-serif tracking-normal text-[#1F1E1D]`，正文 `font-sans text-[#4A463F] leading-relaxed`
- **设计细节**：
  - 极高的大面积留白（Padding `p-8` ~ `p-10`）；
  - 衬线体标题（`font-serif`）搭配高可读性现代无衬线正文；
  - 避免任何强烈的霓虹反光，全面采用哑光亲肤质感。

---

### 预设 C：年轻潮流与新消费活力 (Trendy & Gen-Z)
- **典型品牌**：Nike、喜茶 (HEYTEA)、泡泡玛特 (POP MART)、Lululemon、Fenty Beauty
- **视觉气质**：高唤醒、明快、张力十足、社交网感
- **配色规范 (Tailwind Classes & Hex)**：
  - 背景底色：`bg-[#FAFAFB]`（明净米灰）配合活力局部微渐变
  - 容器卡片：`bg-white rounded-3xl border border-slate-100 shadow-[0_10px_30px_-10px_rgba(0,0,0,0.06)]`
  - 核心主色：`bg-[#FF4D4D]`（元气朱红）或 `bg-[#7B2CBF]`（电波紫）
  - 辅助强调：`bg-[#FFD166]`（明黄标贴）、`text-[#06D6A0]`（活力青薄荷）
  - 文字层级：大字号粗体标题 `font-black tracking-tight text-slate-900`
- **设计细节**：
  - 现代大圆角（`rounded-2xl` ~ `rounded-3xl`）；
  - 标贴式胶囊徽章（`rounded-full px-4 py-1.5 font-bold uppercase text-xs`）；
  - 选项卡切换时具备弹性过渡动效（`transition-all duration-300 ease-out`）。

---

### 预设 D：高端奢华与殿堂美学 (Luxury & Prestige)
- **典型品牌**：Hermès、Chanel、劳力士、麦卡伦威士忌
- **视觉气质**：沉稳庄重、厚重历史感、仪式感、权威度
- **配色规范 (Tailwind Classes & Hex)**：
  - 背景底色：`bg-[#0F1115]`（曜石哑光黑）或 `bg-[#FAF8F5]`（象牙白）
  - 容器卡片：`bg-[#161920] border border-[#2D3342]` 搭配 `hover:border-[#C5A880]/50`
  - 核心主色：`text-[#C5A880]`（香槟香槟金）与 `text-slate-100`
  - 辅助强调：`bg-[#C5A880]`、`border-[#C5A880]/40`
  - 文字层级：标题 `font-serif tracking-widest uppercase`，副标 `tracking-wider`
- **设计细节**：
  - 极细金/银微边框、宽字距（`tracking-widest`）；
  - 精致克制的阴影与装饰衬线线条。

---

### 预设 E：未来出行与清洁能源 (Mobility & Clean Tech)
- **典型品牌**：蔚来 (NIO)、极氪 (ZEEKR)、极星 (Polestar)、理想
- **视觉气质**：纯净无界、天空与大地视野、科技人文温度
- **配色规范 (Tailwind Classes & Hex)**：
  - 背景底色：`bg-[#0B1320]`（星空深蓝）或 `bg-[#F0F4F8]`（天际冰灰）
  - 容器卡片：`bg-white/80 dark:bg-[#131D2E]/80 backdrop-blur-lg border border-sky-900/30`
  - 核心主色：`text-[#00B4D8]`（极光冰蓝）与 `text-[#0077B6]`
  - 辅助强调：`bg-emerald-400/20 text-emerald-400`（生态绿能）
  - 文字层级：标题 `font-sans font-medium tracking-tight`

---

## 2. 纯前端零依赖组件规范

### 2.1 Tailwind CSS 快速引入
看板直接引入 Tailwind CDN，并在头部注入基础变量与自适应配置：
```html
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    darkMode: 'class',
    theme: {
      extend: {
        fontFamily: {
          sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
          serif: ['Newsreader', 'Georgia', 'serif'],
          mono: ['JetBrains Mono', 'Menlo', 'monospace']
        }
      }
    }
  }
</script>
```

### 2.2 SVG 图标最佳实践
杜绝引入笨重的外部字体文件，统一采用内嵌 SVG（Lucide 风格，尺寸 `w-5 h-5` 或 `w-4 h-4`，`stroke-width="1.8"`）。常用图标包含：
- 洞察/闪电：`Target`, `Zap`, `Compass`
- 四象限/坐标：`Grid`, `Layers`, `Crosshair`
- 概念/选项卡：`Sparkles`, `Flame`, `Shield`
- 触点/链路：`Send`, `Flag`, `Share2`

### 2.3 动态心智四象限自绘规范 (Positioning Matrix)
采用纯原生 SVG + HTML 悬浮气泡，保证零外部图表库依赖：
- 坐标轴：横轴与纵轴居中交叉，带两端极性标签（如“理性功能 ⟷ 感性共鸣”、“传统说教 ⟷ 伙伴平视”）；
- 象限底色：四块轻微色彩过渡的圆角矩形底板，标出象限属性（如“红海防守区”、“蓝海真空区”、“溢价高地”）；
- 品牌散点：
  - 竞品点：灰色或低饱和圆点（带微弱光晕与竞品名称标签）；
  - 本品点：品牌高亮强调色（带脉冲动画波纹 `animate-ping` 与高亮 Badge）；
- 交互能力：鼠标悬停在圆点上时，动态显示浮层（包含竞品定位、用户痛点、本品反超破局点）。

---

## 3. 打印与 PDF 导出排版优化 (@media print)

比稿看板必须支持直接带去客户会议室投影或一键打印：
```css
@media print {
  /* 隐藏交互工具栏、切换按钮与装饰阴影 */
  .no-print, nav, button, #toast {
    display: none !important;
  }
  body {
    background: white !important;
    color: black !important;
    padding: 0 !important;
  }
  /* 强制展开所有选项卡，使三大 Core Idea 平铺展现 */
  .tab-pane {
    display: block !important;
    opacity: 1 !important;
    page-break-inside: avoid;
    margin-bottom: 2rem;
  }
  /* 避免卡片跨页截断 */
  .print-avoid-break {
    page-break-inside: avoid;
  }
}
```
