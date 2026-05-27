# 稿定 UI 设计标准

> 版本：v1.0  
> 日期：2026-05-27  
> 状态：已实施

---

## 一、设计原则

### 1.1 核心理念

- **信息优先**：界面设计以内容传达效率为最高优先级
- **一致性**：同类元素使用统一的样式、间距和交互模式
- **直觉性**：用户无需学习即可理解界面操作
- **响应性**：界面在不同设备和屏幕尺寸下保持良好体验

### 1.2 设计目标

| 目标 | 描述 |
|------|------|
| 可读性 | 文字清晰易读，层级分明 |
| 可操作性 | 按钮、输入框等交互元素易于点击和操作 |
| 可发现性 | 重要功能和状态一目了然 |
| 美观性 | 视觉设计专业、现代、符合审美 |

---

## 二、颜色系统

### 2.1 品牌色

```css
--primary: #1a73e8        /* 主色 - Google Blue */
--primary-hover: #1557b0  /* 主色悬停 */
--primary-light: #e8f0fe  /* 主色浅色背景 */
--primary-dark: #0d47a1   /* 主色深色 */
```

**使用场景**：
- 主要按钮、链接、选中状态
- 进度条、重要信息高亮
- 导航栏当前项

### 2.2 语义色

```css
--success: #1e7e34        /* 成功 - 绿色 */
--success-light: #e6f4ea  /* 成功浅色背景 */
--danger: #c5221f         /* 危险/错误 - 红色 */
--danger-light: #fce8e6   /* 危险浅色背景 */
--warning: #f9a825        /* 警告 - 黄色 */
--warning-light: #fff8e1  /* 警告浅色背景 */
```

**使用场景**：
| 颜色 | 场景 |
|------|------|
| 成功 | 完成状态、通过操作、正向指标 |
| 危险 | 错误状态、驳回操作、删除确认 |
| 警告 | 待处理状态、超时提醒、阈值预警 |

### 2.3 中性色

```css
--text-primary: #1a1a2e   /* 主要文字 - 深色 */
--text-secondary: #555    /* 次要文字 */
--text-tertiary: #888     /* 辅助文字 */
--text-disabled: #bbb     /* 禁用文字 */

--bg-primary: #f5f6fa     /* 页面背景 */
--bg-card: #ffffff        /* 卡片背景 */
--bg-hover: #f8f9fa       /* 悬停背景 */
--bg-active: #f0f1f5      /* 激活背景 */

--border-color: #e0e0e0   /* 边框颜色 */
--divider: #f0f0f0        /* 分隔线 */
```

---

## 三、字体系统

### 3.1 字体栈

```css
--font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 
               'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 
               sans-serif;
--font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;
```

### 3.2 字号规范

| 变量 | 大小 | 使用场景 |
|------|------|---------|
| `--text-xs` | 11px | 徽章、极小辅助文字 |
| `--text-sm` | 12px | 标签、时间戳、次要信息 |
| `--text-base` | 13px | 正文默认 |
| `--text-md` | 14px | 按钮、输入框、导航 |
| `--text-lg` | 15px | 卡片标题、小标题 |
| `--text-xl` | 16px | 文章标题 |
| `--text-2xl` | 18px | 页面副标题 |
| `--text-3xl` | 20px | 页面主标题 |
| `--text-4xl` | 24px | 大数字展示 |
| `--text-5xl` | 28px | 特大数字展示 |

### 3.3 字重规范

| 字重 | 值 | 使用场景 |
|------|-----|---------|
| Regular | 400 | 正文、次要文字 |
| Medium | 500 | 标签、按钮、强调文字 |
| Semibold | 600 | 标题、重要数字 |
| Bold | 700 | 页面标题、大数字 |

---

## 四、间距系统

### 4.1 间距变量

```css
--space-xs: 4px     /* 极小间距 - 图标与文字 */
--space-sm: 8px     /* 小间距 - 元素内部 */
--space-md: 12px    /* 中间距 - 相关元素间 */
--space-lg: 16px    /* 大间距 - 组件内部分组 */
--space-xl: 20px    /* 超大间距 - 卡片内边距 */
--space-2xl: 24px   /* 特大间距 - 区块间距 */
--space-3xl: 32px   /* 巨大间距 - 页面区域间距 */
--space-4xl: 40px   /* 最大间距 - 空状态填充 */
```

### 4.2 使用规范

| 场景 | 推荐间距 |
|------|---------|
| 卡片内边距 | `--space-xl` (20px) |
| 卡片之间 | `--space-lg` (16px) |
| 按钮内边距 | `--space-sm` `--space-lg` (8px 16px) |
| 输入框内边距 | `--space-sm` `--space-lg` (8px 16px) |
| 图标与文字 | `--space-xs` `--space-sm` (4-8px) |
| 表单项之间 | `--space-md` `--space-lg` (12-16px) |
| 页面区域之间 | `--space-xl` `--space-2xl` (20-24px) |

---

## 五、圆角系统

### 5.1 圆角变量

```css
--radius-sm: 4px      /* 小圆角 - 标签、小按钮 */
--radius-md: 6px      /* 中圆角 - 按钮、输入框 */
--radius-lg: 8px      /* 大圆角 - 卡片内部元素 */
--radius-xl: 12px     /* 超大圆角 - 卡片 */
--radius-2xl: 16px    /* 特大圆角 - 大容器 */
--radius-full: 9999px /* 全圆 - 徽章、圆形按钮 */
```

### 5.2 使用规范

| 元素 | 圆角 |
|------|------|
| 卡片 | `--radius-xl` (12px) |
| 按钮 | `--radius-md` (6px) |
| 输入框 | `--radius-lg` (8px) |
| 徽章 | `--radius-full` (全圆) |
| 头像 | `--radius-full` (全圆) |
| 工具提示 | `--radius-md` (6px) |

---

## 六、阴影系统

### 6.1 阴影变量

```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05)    /* 微阴影 */
--shadow-md: 0 1px 4px rgba(0, 0, 0, 0.06)    /* 小阴影 - 卡片默认 */
--shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.08)   /* 中阴影 - 悬停状态 */
--shadow-xl: 0 8px 24px rgba(0, 0, 0, 0.12)   /* 大阴影 - 弹出层 */
```

### 6.2 使用规范

| 场景 | 阴影 |
|------|------|
| 卡片默认 | `--shadow-md` |
| 卡片悬停 | `--shadow-lg` |
| 下拉菜单 | `--shadow-xl` |
| 模态框 | `--shadow-xl` |
| 按钮悬停 | `--shadow-md` |

---

## 七、组件规范

### 7.1 卡片 (Card)

```css
.card {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: var(--space-xl);
  box-shadow: var(--shadow-md);
  transition: box-shadow var(--transition-normal);
}

.card:hover {
  box-shadow: var(--shadow-lg);
}
```

**使用规范**：
- 每个独立信息区块使用卡片容器
- 卡片内部使用 `--space-xl` 内边距
- 卡片之间使用 `--space-lg` 间距
- 可交互卡片添加悬停效果

### 7.2 按钮 (Button)

**变体**：

| 变体 | 类名 | 使用场景 |
|------|------|---------|
| 主要 | `.btn-primary` | 主要操作（确认、提交） |
| 成功 | `.btn-success` | 正向操作（通过、发布） |
| 危险 | `.btn-danger` | 危险操作（驳回、删除） |
| 幽灵 | `.btn-ghost` | 次要操作（取消、关闭） |

**尺寸**：

| 尺寸 | 类名 | 内边距 | 字号 |
|------|------|--------|------|
| 小 | `.btn-sm` | 4px 12px | 12px |
| 默认 | `.btn` | 8px 16px | 13px |
| 大 | `.btn-lg` | 12px 20px | 14px |

**状态**：
- 默认：实色背景
- 悬停：颜色加深 + 上移 1px + 阴影
- 禁用：50% 透明度 + 禁止光标
- 加载：显示旋转图标

### 7.3 输入框 (Input)

```css
.input {
  width: 100%;
  padding: var(--space-sm) var(--space-lg);
  font-size: var(--text-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  transition: all var(--transition-fast);
}

.input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-light);
}
```

**使用规范**：
- 输入框宽度 100% 填充容器
- 聚焦时显示蓝色边框和光晕
- 占位符使用 `--text-disabled` 颜色
- 错误状态使用 `--danger` 颜色边框

### 7.4 徽章 (Badge)

**变体**：

| 变体 | 类名 | 使用场景 |
|------|------|---------|
| 主要 | `.badge-primary` | 信息标签 |
| 成功 | `.badge-success` | 完成状态 |
| 危险 | `.badge-danger` | 错误状态 |
| 警告 | `.badge-warning` | 待处理状态 |
| 中性 | `.badge-neutral` | 默认状态 |

**使用规范**：
- 徽章使用全圆角 (`--radius-full`)
- 内边距：2px 10px (小) / 4px 12px (中)
- 字号：12px
- 字重：500

### 7.5 状态徽章 (StatusBadge)

```vue
<StatusBadge status="completed" size="md" />
```

**状态映射**：

| 状态 | 图标 | 颜色 | 标签 |
|------|------|------|------|
| completed | ✅ | 成功绿 | 完成 |
| running | ⏳ | 主色蓝 | 运行中 |
| pending | ⏸️ | 警告黄 | 待处理 |
| failed | ❌ | 危险红 | 失败 |
| idle | 💤 | 中性灰 | 空闲 |

### 7.6 进度条 (Progress Bar)

```css
.progress-bar {
  height: 6px;
  background: var(--bg-hover);
  border-radius: var(--radius-full);
}

.progress-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}
```

**颜色规则**：
- 0-60%：成功绿 (`--success`)
- 60-80%：警告黄 (`--warning`)
- 80-100%：危险红 (`--danger`)

---

## 八、布局规范

### 8.1 页面布局

```css
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  height: 56px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-nav {
  position: sticky;
  top: 56px;
  z-index: 99;
}

.app-main {
  flex: 1;
  padding: var(--space-xl) var(--space-lg);
}

.content-container {
  max-width: 1200px;
  margin: 0 auto;
}
```

### 8.2 网格布局

```css
.grid {
  display: grid;
  gap: var(--space-lg);
}

.grid-auto-fill {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
```

**使用规范**：
- 卡片网格：最小宽度 280px，自动填充
- 统计卡片：2-4 列等宽
- 表单布局：单列或双列

### 8.3 Flex 布局

```css
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-sm { gap: var(--space-sm); }
.gap-md { gap: var(--space-md); }
.gap-lg { gap: var(--space-lg); }
```

---

## 九、动画规范

### 9.1 过渡时间

```css
--transition-fast: 150ms ease    /* 快速 - 按钮、链接 */
--transition-normal: 200ms ease  /* 正常 - 卡片、面板 */
--transition-slow: 300ms ease    /* 慢速 - 进度条、展开 */
```

### 9.2 使用场景

| 元素 | 过渡时间 | 过渡属性 |
|------|---------|---------|
| 按钮悬停 | 150ms | background, transform, box-shadow |
| 卡片悬停 | 200ms | box-shadow |
| 输入框聚焦 | 150ms | border-color, box-shadow |
| 进度条 | 300ms | width |
| 展开/折叠 | 200ms | height, opacity |
| 页面切换 | 200ms | opacity |

### 9.3 动画效果

```css
/* 旋转动画 - 加载状态 */
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 淡入淡出 - 页面切换 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-normal);
}

/* 滑入滑出 - 面板展开 */
.slide-enter-active,
.slide-leave-active {
  transition: transform var(--transition-normal), 
              opacity var(--transition-normal);
}
```

---

## 十、响应式规范

### 10.1 断点定义

| 断点 | 宽度 | 设备 |
|------|------|------|
| 移动端 | < 480px | 手机 |
| 平板 | < 768px | 平板、小屏笔记本 |
| 桌面 | ≥ 769px | 桌面显示器 |

### 10.2 响应式规则

**移动端 (< 768px)**：
- 单列布局
- 隐藏次要信息
- 导航横向滚动
- 增大点击区域

**平板 (768px - 1024px)**：
- 2 列网格
- 保持主要功能可见
- 适当缩减间距

**桌面 (> 1024px)**：
- 多列网格
- 完整功能展示
- 标准间距

### 10.3 工具类

```css
.hide-mobile { display: none !important; }  /* 移动端隐藏 */
.hide-desktop { display: none !important; } /* 桌面端隐藏 */
```

---

## 十一、交互规范

### 11.1 反馈机制

| 操作 | 反馈 |
|------|------|
| 点击按钮 | 按钮上移 + 阴影增强 |
| 悬停卡片 | 阴影增强 |
| 聚焦输入 | 蓝色边框 + 光晕 |
| 加载中 | 旋转图标 + 文字 |
| 操作成功 | 绿色提示 + 自动消失 |
| 操作失败 | 红色提示 + 手动关闭 |

### 11.2 空状态设计

```html
<div class="empty-state">
  <div class="empty-state-icon">📭</div>
  <div class="empty-state-title">暂无数据</div>
  <div class="empty-state-description">
    等待数据加载或执行相关操作
  </div>
</div>
```

**设计规范**：
- 图标：48px，50% 透明度
- 标题：15px，主要文字颜色
- 描述：14px，辅助文字颜色
- 居中显示，上下 40px 内边距

### 11.3 加载状态

```html
<div class="loading">
  <div class="loading-spinner"></div>
  <span>加载中...</span>
</div>
```

**设计规范**：
- 旋转图标：16px (小) / 24px (大)
- 文字：14px，辅助文字颜色
- 居中显示

---

## 十二、代码规范

### 12.1 CSS 变量使用

**必须使用变量**：
- 颜色值
- 间距值
- 字号值
- 圆角值
- 阴影值

**禁止硬编码**：
```css
/* ❌ 错误 */
color: #1a73e8;
padding: 20px;

/* ✅ 正确 */
color: var(--primary);
padding: var(--space-xl);
```

### 12.2 组件样式

**使用 scoped 样式**：
```vue
<style scoped>
.component-name {
  /* 样式 */
}
</style>
```

**命名规范**：
- 使用 kebab-case
- 组件名作为前缀
- 避免深层嵌套选择器

### 12.3 响应式编写

**移动优先**：
```css
/* 默认移动端样式 */
.element {
  padding: var(--space-md);
}

/* 平板及以上 */
@media (min-width: 768px) {
  .element {
    padding: var(--space-xl);
  }
}
```

---

## 十三、可访问性

### 13.1 颜色对比度

- 正文文字：至少 4.5:1 对比度
- 大文字：至少 3:1 对比度
- 交互元素：至少 3:1 对比度

### 13.2 键盘导航

- 所有交互元素可聚焦
- 焦点状态清晰可见
- Tab 顺序符合逻辑

### 13.3 屏幕阅读器

- 图标添加 `title` 属性
- 图片添加 `alt` 属性
- 表单关联 `label`

---

## 附录：快速参考

### 颜色速查

| 用途 | 颜色 |
|------|------|
| 主要按钮 | `var(--primary)` |
| 成功状态 | `var(--success)` |
| 错误状态 | `var(--danger)` |
| 警告状态 | `var(--warning)` |
| 主要文字 | `var(--text-primary)` |
| 次要文字 | `var(--text-secondary)` |
| 辅助文字 | `var(--text-tertiary)` |
| 页面背景 | `var(--bg-primary)` |
| 卡片背景 | `var(--bg-card)` |

### 间距速查

| 场景 | 间距 |
|------|------|
| 卡片内边距 | `var(--space-xl)` |
| 卡片间距 | `var(--space-lg)` |
| 按钮内边距 | `var(--space-sm) var(--space-lg)` |
| 元素间距 | `var(--space-md)` |
| 区域间距 | `var(--space-2xl)` |

### 字号速查

| 场景 | 字号 |
|------|------|
| 页面标题 | `var(--text-3xl)` |
| 卡片标题 | `var(--text-lg)` |
| 正文 | `var(--text-md)` |
| 辅助文字 | `var(--text-sm)` |
| 徽章 | `var(--text-xs)` |
