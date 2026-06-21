"""
订单查询工具
"""

from langchain_core.tools import tool
from datetime import datetime, timedelta

# 模拟数据库
ORDERS = {
    "user001": [
        {
            "order_id": "OR20260618001",
            "product": "iPhone 15 Pro 256G 钛金色",
            "price": 8999.00,
            "status": "已发货",
            "date": "2026-06-15",
            "express": "顺丰速运 SF1234567890",
            "estimate_delivery": "2026-06-19"
        },
        {
            "order_id": "OR20260612002",
            "product": "AirPods Pro 2",
            "price": 1899.00,
            "status": "已送达",
            "date": "2026-06-12",
            "express": None,
            "estimate_delivery": "2026-06-14"
        },
        {
            "order_id": "OR20260608003",
            "product": "MacBook Pro 14寸 M3",
            "price": 14999.00,
            "status": "已签收",
            "date": "2026-06-08",
            "express": "顺丰速运 SF9876543210",
            "estimate_delivery": "2026-06-10"
        },
    ],
    "user002": [
        {
            "order_id": "OR20260617004",
            "product": "iPad Air 5 64G WiFi",
            "price": 4399.00,
            "status": "处理中",
            "date": "2026-06-17",
            "express": None,
            "estimate_delivery": None
        },
    ],
    "user003": [
        {
            "order_id": "OR20260616005",
            "product": "Apple Watch S9",
            "price": 3299.00,
            "status": "已发货",
            "date": "2026-06-16",
            "express": "圆通速递 YT5555555555",
            "estimate_delivery": "2026-06-20"
        },
    ],
}

# 物流状态映射
LOGISTICS_STATUS = {
    "已发货": "包裹已从仓库发出，正在运输途中",
    "运输中": "包裹运输中，预计明天送达",
    "派送中": "快递员正在为您派送，请保持手机畅通",
    "已签收": "包裹已签收，感谢您购买我们的商品",
    "处理中": "订单正在处理中，预计1-2个工作日发货",
}


@tool
async def query_orders(user_id: str) -> str:
    """查询客户的所有订单

    Args:
        user_id: 客户ID
    """
    orders = ORDERS.get(user_id, [])

    if not orders:
        return f"客户 {user_id} 暂无订单记录。"

    result = f"客户 {user_id} 的订单记录（共 {len(orders)} 笔）：\n\n"

    for order in orders:
        logistics_info = LOGISTICS_STATUS.get(order["status"], "")
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"订单号：{order['order_id']}\n"
        result += f"商品：{order['product']}\n"
        result += f"金额：¥{order['price']:.2f}\n"
        result += f"状态：{order['status']}\n"
        result += f"下单时间：{order['date']}\n"

        if order["express"]:
            result += f"快递：{order['express']}\n"

        if order["estimate_delivery"]:
            result += f"预计送达：{order['estimate_delivery']}\n"

        if logistics_info:
            result += f"物流动态：{logistics_info}\n"

        result += "\n"

    return result


@tool
async def get_order_status(order_id: str) -> str:
    """查询单个订单的详细状态

    Args:
        order_id: 订单号，如 OR20260618001
    """
    # 在所有订单中查找
    for user_id, orders in ORDERS.items():
        for order in orders:
            if order["order_id"] == order_id:
                logistics_info = LOGISTICS_STATUS.get(order["status"], "")

                result = f"""订单详情：
━━━━━━━━━━━━━━━━━━━━━━━━━━
订单号：{order['order_id']}
客户ID：{user_id}
商品：{order['product']}
金额：¥{order['price']:.2f}
状态：{order['status']}
下单时间：{order['date']}
"""

                if order["express"]:
                    result += f"快递单号：{order['express']}\n"

                if order["estimate_delivery"]:
                    result += f"预计送达：{order['estimate_delivery']}\n"

                if logistics_info:
                    result += f"\n物流动态：{logistics_info}\n"

                return result

    return f"未找到订单 {order_id}。请确认订单号是否正确。"
