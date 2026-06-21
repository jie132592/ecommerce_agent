"""
升级工单工具
"""

from langchain_core.tools import tool
from datetime import datetime
import random

# 模拟工单存储
TICKETS = {}


@tool
async def create_ticket(user_id: str, problem: str, order_id: str = None) -> str:
    """创建客服工单

    当客户问题无法立即解决时，创建工单转交人工处理

    Args:
        user_id: 客户ID
        problem: 问题描述
        order_id: 关联订单号（可选）
    """
    # 生成工单号
    ticket_id = f"TKT{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"

    # 模拟创建工单
    TICKETS[ticket_id] = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "problem": problem,
        "order_id": order_id,
        "status": "待处理",
        "created_at": datetime.now().isoformat(),
        "priority": "normal",
    }

    return f"""已为您创建工单：

━━━━━━━━━━━━━━━━━━━━━━━━━━
工单号：{ticket_id}
客户ID：{user_id}
{"关联订单：" + order_id if order_id else ""}
问题：{problem}
状态：待处理
━━━━━━━━━━━━━━━━━━━━━━━━━━

我们的工作人员会在 24 小时内处理您的请求。

您可以：
• 拨打客服热线：400-123-4567
• 关注公众号「客服小助手」实时查询进度

感谢您的耐心等待！"""


@tool
async def transfer_to_human(reason: str) -> str:
    """转接人工客服

    当 AI 无法解决问题时，转接人工客服

    Args:
        reason: 转接原因
    """
    ticket_id = f"HUM{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"

    return f"""正在为您转接人工客服...

━━━━━━━━━━━━━━━━━━━━━━━━━━
转接原因：{reason}
排队号码：{ticket_id}
预计等待：3-5 分钟
━━━━━━━━━━━━━━━━━━━━━━━━━━

在等待期间，您可以：
• 准备好订单号或问题截图
• 继续描述您的问题

人工客服将尽快为您处理！

💬 也可以拨打热线：400-123-4567（24小时）"""
