# 渐进式重构计划

## 当前状态

- ✅ **阶段1已完成**：PipelineLogger 工具类重构（2024-04-11）
- ✅ **阶段2已完成**：MainWindow 组件化重构（2024-04-11）
- ⏳ **阶段3待定**：核心服务层重构
- ⏳ **阶段4待定**：其他优化项

**详细完成情况请查看 `REFACTORING_SUMMARY.md`**

---

## 原则
1. **每次只改一个文件**
2. **改完立即测试**
3. **确认无问题再继续**
4. **保持 100% 向后兼容**

---

## 阶段 1：零风险重构 ✅ 已完成

### 完成内容
- [x] 创建 `utils/logger.py` - PipelineLogger 工具类
- [x] 重构 `services/pipeline.py` - 统一日志调用
- [x] 重构 `services/batch_translation.py` - 统一日志调用
- [x] 重构 `services/task_service.py` - 统一日志调用
- [x] 所有 264 个测试通过

### 成果
- 消除 ~150行重复日志代码
- 代码从 2078行 减少到 2066行 (-12行)
```

**回滚方案：** 如果有问题，用 git 回退这一次提交

**预期效果：**
- 功能：完全不变
- 代码：减少 ~50 行
- 可读性：提升

---

#### 1.2 重构 `batch_translation.py`（20 分钟）

**改动范围：** `execute()` 和 `_execute_plan_items()` 方法

**测试方法：**
```bash
pytest tests/test_batch_translation.py -v

# 手动测试：批量翻译
# 在 GUI 中选择目录批量翻译，观察日志
```

**预期效果：** 减少 ~30 行

---

#### 1.3 重构 `task_service.py`（30 分钟）

**改动范围：** `translate_prepared_document()` 方法

**测试方法：**
```bash
pytest tests/test_task_service.py -v
```

**预期效果：** 减少 ~40 行

---

#### 1.4 创建测试确保兼容性（15 分钟）

```python
# tests/test_logger_compatibility.py
def test_logger_backward_compatible():
    """确保新 Logger 与旧方式行为完全一致"""
    # ... 测试代码
```

**总计阶段 1：** 
- 时间：~2 小时
- 减少代码：~120 行
- 风险：极低（只是提取重复代码）

---

## 阶段 2：低风险重构（下周完成）

### 2.1 提取错误处理装饰器（1 小时）

**新增文件：** `utils/error_handling.py`

```python
def pipeline_error_handler(stage: str):
    """装饰器：统一处理 pipeline 错误"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (OSError, ValueError) as exc:
                raise TranslationPipelineError(stage, str(exc)) from exc
        return wrapper
    return decorator
```

**应用到：**
- `pipeline.py` 的文件读取方法
- `batch_translation.py` 的目录扫描方法

**测试：** 运行所有测试，确保错误处理行为不变

**预期效果：** 减少 ~100 行

---

### 2.2 提取进度计算工具（30 分钟）

**新增文件：** `utils/progress.py`

```python
class ProgressCalculator:
    @staticmethod
    def linear(completed: int, total: int, start: int, end: int) -> int:
        """线性进度计算"""
        if total <= 0:
            return start
        span = end - start
        return min(end, start + int((completed / total) * span))
```

**应用到：**
- `pipeline.py` 的 `translation_progress()` 方法
- `batch_translation.py` 的进度计算

**预期效果：** 减少 ~50 行

---

**总计阶段 2：**
- 时间：~2 小时
- 减少代码：~150 行
- 风险：低

---

## 阶段 3：中风险重构（下下周完成）

### 3.1 拆分 `main_window.py` - 提取日志管理（2 小时）

**新增文件：** `ui/task_logger.py`

```python
class TaskLogger:
    """管理任务日志文件的创建、写入、查看"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
    
    def create_log_file(self) -> Path:
        """创建新的日志文件"""
        ...
    
    def append(self, message: str) -> None:
        """追加日志"""
        ...
    
    def show_viewer(self, parent: QWidget) -> None:
        """显示日志查看器"""
        ...
```

**改动：** `main_window.py` 中所有日志相关代码委托给 `TaskLogger`

**测试：**
```bash
pytest tests/test_main_window.py -v

# 手动测试：
# 1. 翻译任务，查看日志文件是否正常创建
# 2. 点击"查看详细日志"，确认对话框正常显示
# 3. 批量翻译，确认日志正常
```

**预期效果：** 
- `main_window.py` 减少 ~150 行
- 新增 `task_logger.py` ~100 行
- 净减少：~50 行
- 职责更清晰

---

### 3.2 拆分 `main_window.py` - 提取输入验证（1 小时）

**改动：** 将验证逻辑移到 `validator.py`，`main_window.py` 只调用

**预期效果：** 减少 ~80 行

---

**总计阶段 3：**
- 时间：~4 小时
- 减少代码：~130 行
- 风险：中（涉及 UI，需要仔细测试）

---

## 阶段 4：高风险重构（未来版本）

### 4.1 重构 `task_service.py` - 职责分离

**拆分为：**
- `task_service.py` - 核心编排（300 行）
- `batch_executor.py` - 批量执行（250 行）
- `translation_validator.py` - 验证逻辑（200 行）
- `retry_handler.py` - 重试策略（150 行）

**风险：** 高（核心业务逻辑）
**时间：** 2-3 天
**建议：** 在新版本中进行，充分测试

---

### 4.2 重构 `protector.py` - 策略模式

**拆分为：**
- `protector.py` - 核心协调（200 行）
- `protection_strategies.py` - 各种保护策略（500 行）

**风险：** 高（核心功能）
**时间：** 2 天
**建议：** 在新版本中进行

---

## 执行建议

### 本周（阶段 1）
1. 今天：重构 `pipeline.py`，测试
2. 明天：重构 `batch_translation.py` 和 `task_service.py`，测试
3. 后天：写兼容性测试，确保一切正常

### 下周（阶段 2）
1. 提取错误处理装饰器
2. 提取进度计算工具
3. 全面测试

### 下下周（阶段 3）
1. 拆分 `main_window.py` 日志管理
2. 拆分 `main_window.py` 验证逻辑
3. 充分测试 UI 功能

### 未来版本（阶段 4）
- 等前面的重构稳定后再考虑
- 需要更充分的测试覆盖

---

## 测试清单

每次重构后都要跑这个清单：

### 自动化测试
```bash
# 运行所有测试
pytest tests/ -v

# 检查测试覆盖率
pytest --cov=doc_translation_tool --cov-report=term-missing
```

### 手动测试
- [ ] 单文件翻译（中译英）
- [ ] 单文件翻译（英译中）
- [ ] 目录批量翻译
- [ ] 查看详细日志
- [ ] 编辑术语表
- [ ] 编辑模型配置
- [ ] 翻译失败时的错误提示
- [ ] 大文件翻译（测试进度显示）
- [ ] 中断翻译后重新开始（测试缓存恢复）

---

## Git 提交策略

每完成一个小步骤就提交：

```bash
git add doc_translation_tool/utils/logger.py
git commit -m "refactor: 添加 PipelineLogger 工具类"

git add doc_translation_tool/services/pipeline.py
git commit -m "refactor: pipeline.py 使用 PipelineLogger 减少重复代码"

# 如果发现问题，可以轻松回退
git revert HEAD
```

---

## 预期总效果

| 阶段 | 时间 | 减少代码 | 风险 | 状态 |
|------|------|---------|------|------|
| 阶段 1 | 2h | -120 行 | 极低 | 本周 |
| 阶段 2 | 2h | -150 行 | 低 | 下周 |
| 阶段 3 | 4h | -130 行 | 中 | 下下周 |
| 阶段 4 | 5天 | -500 行 | 高 | 未来 |
| **总计** | **~6 天** | **-900 行** | - | - |

**最终：** 从 9051 行精简到 ~8150 行（-10%），代码质量显著提升

---

## 注意事项

1. **不要一次改太多** - 每次只改一个文件
2. **改完立即测试** - 不要积累多个改动
3. **保留旧代码注释** - 方便回滚
4. **更新文档** - 如果改了公共 API
5. **通知团队** - 如果是多人协作

---

## 需要帮助时

如果遇到问题：
1. 先回退到上一个稳定版本
2. 检查测试输出
3. 对比重构前后的行为差异
4. 问我具体问题，我会帮你解决
