"""
测试新的 Logger 工具类是否与旧方式完全兼容

运行方法：
    pytest tests/test_logger_compatibility.py -v
"""

import pytest
from doc_translation_tool.utils.logger import PipelineLogger, ProgressReporter


class TestLoggerCompatibility:
    """验证新 Logger 与旧方式行为完全一致"""

    def test_logger_with_callback(self):
        """测试有回调函数时的行为"""
        logs = []

        def callback(msg):
            logs.append(msg)

        logger = PipelineLogger(callback)
        logger.file("测试消息")

        assert logs == ["[文件] 测试消息"]

    def test_logger_without_callback(self):
        """测试无回调函数时不会报错"""
        logger = PipelineLogger(None)
        logger.file("测试消息")  # 不应该抛出异常

    def test_logger_all_stages(self):
        """测试所有阶段前缀"""
        logs = []
        logger = PipelineLogger(logs.append)

        logger.file("文件消息")
        logger.config("配置消息")
        logger.model("模型消息")
        logger.parse("解析消息")
        logger.translate("翻译消息")
        logger.output("输出消息")
        logger.complete("完成消息")
        logger.batch("批量消息")
        logger.resume("续跑消息")
        logger.glossary("术语消息")
        logger.stats("统计消息")

        expected = [
            "[文件] 文件消息",
            "[配置] 配置消息",
            "[模型] 模型消息",
            "[解析] 解析消息",
            "[翻译] 翻译消息",
            "[输出] 输出消息",
            "[完成] 完成消息",
            "[批量] 批量消息",
            "[续跑] 续跑消息",
            "[术语] 术语消息",
            "[stats] 统计消息",
        ]

        assert logs == expected

    def test_progress_reporter_with_callback(self):
        """测试进度报告器有回调时的行为"""
        reports = []

        def callback(msg, percent):
            reports.append((msg, percent))

        progress = ProgressReporter(callback)
        progress.report("测试进度", 50)

        assert reports == [("测试进度", 50)]

    def test_progress_reporter_without_callback(self):
        """测试进度报告器无回调时不会报错"""
        progress = ProgressReporter(None)
        progress.report("测试进度", 50)  # 不应该抛出异常

    def test_logger_vs_old_style_equivalence(self):
        """验证新旧方式产生完全相同的输出"""
        old_logs = []
        new_logs = []

        # 旧方式
        def emit_log_old(message: str) -> None:
            if old_logs is not None:
                old_logs.append(message)

        emit_log_old("[文件] 开始读取：test.md")
        emit_log_old("[配置] 模型：gpt-4")
        emit_log_old("[翻译] 片段总数：10")

        # 新方式
        logger = PipelineLogger(new_logs.append)
        logger.file("开始读取：test.md")
        logger.config("模型：gpt-4")
        logger.translate("片段总数：10")

        # 验证完全一致
        assert old_logs == new_logs

    def test_progress_vs_old_style_equivalence(self):
        """验证进度报告新旧方式完全一致"""
        old_progress = []
        new_progress = []

        # 旧方式
        def emit_progress_old(message: str, percent: int) -> None:
            if old_progress is not None:
                old_progress.append((message, percent))

        emit_progress_old("准备翻译任务", 0)
        emit_progress_old("源文件读取完成", 10)
        emit_progress_old("翻译完成", 100)

        # 新方式
        progress = ProgressReporter(lambda m, p: new_progress.append((m, p)))
        progress.report("准备翻译任务", 0)
        progress.report("源文件读取完成", 10)
        progress.report("翻译完成", 100)

        # 验证完全一致
        assert old_progress == new_progress

    def test_logger_with_formatted_strings(self):
        """测试带格式化字符串的日志"""
        logs = []
        logger = PipelineLogger(logs.append)

        file_path = "/path/to/file.md"
        elapsed = 1.23
        count = 42

        logger.file(f"开始读取：{file_path}")
        logger.translate(f"耗时 {elapsed:.2f}s")
        logger.batch(f"已完成 {count} 个文件")

        assert logs == [
            "[文件] 开始读取：/path/to/file.md",
            "[翻译] 耗时 1.23s",
            "[批量] 已完成 42 个文件",
        ]

    def test_logger_thread_safety(self):
        """测试多线程环境下的安全性"""
        import threading

        logs = []
        lock = threading.Lock()

        def thread_safe_callback(msg):
            with lock:
                logs.append(msg)

        logger = PipelineLogger(thread_safe_callback)

        def worker(n):
            for i in range(10):
                logger.log(f"Thread {n} - Message {i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应该有 50 条日志（5 个线程 × 10 条消息）
        assert len(logs) == 50


class TestLoggerEdgeCases:
    """测试边界情况"""

    def test_empty_message(self):
        """测试空消息"""
        logs = []
        logger = PipelineLogger(logs.append)
        logger.file("")
        assert logs == ["[文件] "]

    def test_multiline_message(self):
        """测试多行消息"""
        logs = []
        logger = PipelineLogger(logs.append)
        logger.file("第一行\n第二行\n第三行")
        assert logs == ["[文件] 第一行\n第二行\n第三行"]

    def test_unicode_message(self):
        """测试 Unicode 字符"""
        logs = []
        logger = PipelineLogger(logs.append)
        logger.file("测试中文 🎉 emoji")
        assert logs == ["[文件] 测试中文 🎉 emoji"]

    def test_very_long_message(self):
        """测试超长消息"""
        logs = []
        logger = PipelineLogger(logs.append)
        long_msg = "x" * 10000
        logger.file(long_msg)
        assert logs == [f"[文件] {long_msg}"]

    def test_callback_exception_handling(self):
        """测试回调函数抛出异常时的行为"""

        def bad_callback(msg):
            raise ValueError("回调函数出错")

        logger = PipelineLogger(bad_callback)

        # 应该让异常向上传播（不吞掉异常）
        with pytest.raises(ValueError, match="回调函数出错"):
            logger.file("测试")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
