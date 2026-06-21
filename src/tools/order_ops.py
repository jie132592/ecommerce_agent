"""
订单相关工具（扩展）
"""

from langchain_core.tools import tool
from typing import Optional
from datetime import datetime, timedelta

# 模拟物流数据
LOGISTICS = {
    "SF1234567890": {
        "company": "顺丰速运",
        "status": "派送中",
        "current": "北京市朝阳区 XXX 营业部",
        " ETA": "今天 18:00 前",
        "events": [
            {"time": "2026-06-18 08:00", "location": "北京转运中心", "status": "已发出"},
            {"time": "2026-06-17 20:00", "location": "上海分拨中心", "status": "运输中"},
            {"time": "2026-06-17 15:00", "location": "上海浦东仓库", "status": "已发货"},
        ]
    },
    "YT5555555555": {
        "company": "圆通速递",
        "status": "运输中",
        "current": "杭州转运中心",
        " ETA": "2026-06-20",
        "events": [
            {"time": "2026-06-16 10:00", "location": "广州仓库", "status": "已发货"},
        ]
    },
}


@tool
async def track_delivery(order_id: str) -> str:
    """追踪物流轨迹

    Args:
        order_id: 订单号，如 OR20260618001
    """
    # 简化：从订单获取物流单号
    order_logistics = {
        "OR20260618001": "SF1234567890",
        "OR20260616005": "YT5555555555",
    }

    tracking_no = order_logistics.get(order_id)

    if not tracking_no or tracking_no not in LOGISTICS:
        return f"未找到订单 {order_id} 的物流信息。\n可能原因：\n1. 订单尚未发货\n2. 物流单号录入延迟\n3. 订单号输入有误"

    info = LOGISTICS[tracking_no]

    result = f"""物流追踪：
━━━━━━━━━━━━━━━━━━━━━━━━━━
快递公司：{info['company']}
运单号：{tracking_no}
当前状态：{info['status']}
当前位置：{info['current']}
预计送达：{info.get('ETA', '待更新')}

物流轨迹："""

    for event in info["events"]:
        result += f"\n• {event['time']} | {event['location']} | {event['status']}"

    return result


@tool
async def cancel_order(order_id: str, user_id: str, reason: str) -> str:
    """取消订单

    Args:
        order_id: 订单号
        user_id: 客户ID
        reason: 取消原因
    """
    # 模拟订单状态检查
    can_cancel = True
    order_status = "处理中"

    if order_status == "已发货":
        can_cancel = False
        return f"""订单 {order_id} 无法取消！

原因：订单已发货，快递正在途中。

您可以：
1. 等待收货后申请退货退款
2. 联系快递员拦截（可能产生费用）
3. 拒收快递，让快递员退回"""

    if can_cancel:
        return f"""订单 {order_id} 取消成功！

取消原因：{reason}
退款方式：原路返回（1-7个工作日到账）
退款金额：¥8999.00（已支付金额）

如有疑问，请联系客服。"""


@tool
async def apply_refund(order_id: str, user_id: str, reason: str, amount: float) -> str:
    """申请退款

    Args:
        order_id: 订单号
        user_id: 客户ID
        reason: 退款原因
        amount: 退款金额
    """
    # 生成退款单号
    refund_id = f"REF{datetime.now().strftime('%Y%m%d%H%M%S')}"

    return f"""退款申请已提交！

━━━━━━━━━━━━━━━━━━━━━━━━━━
退款单号：{refund_id}
关联订单：{order_id}
退款金额：¥{amount:.2f}
退款原因：{reason}

退款进度：
• 已提交 → 审核中 → 财务处理 → 退款成功
预计完成时间：1-3个工作日

退款方式：原路返回（1-7个工作日到账）

如有疑问，请保留此退款单号。"""


@tool
async def modify_address(order_id: str, new_address: str, contact_name: str, contact_phone: str) -> str:
    """修改收货地址

    Args:
        order_id: 订单号
        new_address: 新的收货地址
        contact_name: 联系人姓名
        contact_phone: 联系人电话
    """
    # 模拟地址修改
    return f"""收货地址修改成功！

━━━━━━━━━━━━━━━━━━━━━━━━━━
订单号：{order_id}
新收货地址：{new_address}
联系人：{contact_name}
联系电话：{contact_phone}

修改时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

注意：
- 如果订单已发货，地址修改可能需要额外时间
- 新疆、西藏等偏远地区可能影响送达时间"""
