from unittest import TestCase

from app.services import summarizer


class SummaryValidationTest(TestCase):
    def test_accepts_required_insights_table(self) -> None:
        detail = (
            "这是足够长的内容，用于描述论文中的关键观察、方法洞察和实验经验，"
            "并且保留具体结论、适用条件、限制和失败模式。"
        )
        text = "\n".join(
            [
                "| 主题 | 内容 | 出处段落 |",
                "| --- | --- | --- |",
                f"| 现象观察 | {detail} | 摘要 |",
                f"| 方法洞察 | {detail} | 方法-Sec 3 |",
                f"| 实验经验 | {detail} | 实验-Sec 4 |",
            ]
        )

        summarizer._validate_insights_table(text)

    def test_rejects_insights_table_with_preamble(self) -> None:
        detail = (
            "这是足够长的内容，用于描述论文中的关键观察、方法洞察和实验经验，"
            "并且保留具体结论、适用条件、限制和失败模式。"
        )
        text = "\n".join(
            [
                "下面是表格：",
                "| 主题 | 内容 | 出处段落 |",
                "| --- | --- | --- |",
                f"| 现象观察 | {detail} | 摘要 |",
                f"| 方法洞察 | {detail} | 方法-Sec 3 |",
                f"| 实验经验 | {detail} | 实验-Sec 4 |",
            ]
        )

        with self.assertRaises(ValueError):
            summarizer._validate_insights_table(text)

    def test_accepts_three_to_five_followup_items(self) -> None:
        text = "\n".join(
            [
                "- **方向一**：现状/限制：当前方法还有覆盖不足，尚未说明在低资源和跨领域场景中的可靠性。方案：引入对照实验和新的评测协议。风险或难点：数据成本较高。",
                "- **方向二**：现状/限制：模型泛化仍不稳定，且不同数据分布上的表现差异没有被充分解释。方案：比较不同训练目标、模型规模和数据配比。风险或难点：需要严格控制变量。",
                "- **方向三**：现状/限制：失败案例分析不足，难以判断主要错误来自数据、模型还是评测协议。方案：构建错误分类并做定量统计。风险或难点：标注标准可能不一致。",
            ]
        )

        summarizer._validate_followup(text)
