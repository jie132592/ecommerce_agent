"""
发票相关工具
"""

from langchain_core.tools import tool
from typing import Optional
from datetime import datetime, timedelta

# 模拟发票数据
INVOICES = {
    "user001": [
        {"invoice_id": "INV202606001", "order_id": "OR20260608003", "amount": 14999.00, "type": "电子", "status": "已开", "date": "2026-06-10"},
        {"invoice_id": "INV202606002", "order_id": "OR20260612002", "amount": 1899.00, "type": "电子", "status": "已开", "date": "2026-06-14"},
    ],
    "user002": [],
    "user003": [
        {"invoice_id": "INV202606003", "order_id": "OR20260616005", "amount": 3299.00, "type": "纸质", "status": "开具中", "date": "2026-06-18"},
    ],
}


@tool
async def query_invoice(order_id: str) -> str:
    """查询发票

    Args:
        order_id: 订单号
    """
    # 查找发票
    for user_id, invoices in INVOICES.items():
        for inv in invoices:
            if inv["order_id"] == order_id:
                return f"""发票信息：
━━━━━━━━━━━━━━━━━━━━━━━━━━
发票编号：{inv['invoice_id']}
订单编号：{inv['order_id']}
发票金额：¥{inv['amount']:.2f}
发票类型：{inv['type']}发票
状态：{inv['status']}
开票日期：{inv['date']}"""

    return f"未找到订单 {order_id} 的发票信息"


@tool
async def apply_invoice(
    order_id: str,
    invoice_type: str = "电子",
    title_type: str = "个人",
    title: str = "",
    tax_number: str = ""
) -> str:
    """申请发票

    Args:
        order_id: 订单号
        invoice_type: 发票类型，电子/纸质
        title_type: 抬头类型，个人/企业
        title: 发票抬头
        tax_number: 税号（企业发票必填）
    """
    # 生成发票申请单号
    invoice_id = f"INV{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if title_type == "企业" and not tax_number:
        return "企业发票必须填写税号，请重新申请。"

    future_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')

    return f"""发票申请已提交！

━━━━━━━━━━━━━━━━━━━━━━━━━━
申请单号：{invoice_id}
订单编号：{order_id}
发票类型：{invoice_type}发票
抬头类型：{title_type}
发票抬头：{title or '个人'}{(chr(10) + '税号：' + tax_number) if tax_number else ''}
开票时间：预计{future_date}前完成

{'电子发票将发送至您的注册邮箱' if invoice_type == '电子' else '纸质发票将随下次商品寄出'}

如有疑问，请联系客服。"""
