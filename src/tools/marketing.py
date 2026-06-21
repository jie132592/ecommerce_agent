"""
营销相关工具
"""

from langchain_core.tools import tool
from typing import Optional
from datetime import datetime, timedelta

# 模拟营销数据
COUPONS = {
    "C001": {"name": "新人专享券", "type": "折扣", "value": 20, "min_amount": 100, "expire": "2026-07-31"},
    "C002": {"name": "满500减50", "type": "满减", "value": 50, "min_amount": 500, "expire": "2026-06-30"},
    "C003": {"name": "VIP专属85折", "type": "折扣", "value": 15, "min_amount": 0, "expire": "2026-12-31"},
    "C004": {"name": "限时免运费", "type": "运费", "value": 0, "min_amount": 0, "expire": "2026-06-20"},
    "C005": {"name": "生日特惠", "type": "折扣", "value": 10, "min_amount": 0, "expire": "2026-12-31"},
}

POINTS = {
    "user001": 5680,
    "user002": 12350,
    "user003": 500,
}

VIP_LEVELS = {
    "user001": "VIP",
    "user002": "VIP",
    "user003": "普通",
}


@tool
async def search_coupons(
    user_id: str,
    coupon_type: Optional[str] = None,
    only_available: bool = True
) -> str:
    """搜索可用优惠券

    Args:
        user_id: 客户ID
        coupon_type: 优惠券类型筛选，可选：折扣/满减/运费
        only_available: 是否只显示可用优惠券
    """
    today = datetime.now().strftime("%Y-%m-%d")

    results = []
    for cid, coupon in COUPONS.items():
        # 过滤已过期
        if only_available and coupon["expire"] < today:
            continue

        # 过滤类型
        if coupon_type and coupon["type"] != coupon_type:
            continue

        # VIP 专属券过滤
        if "VIP专属" in coupon["name"] and VIP_LEVELS.get(user_id) != "VIP":
            continue

        results.append((cid, coupon))

    if not results:
        return "当前没有符合条件的优惠券"

    result = f"为您找到 {len(results)} 张优惠券：\n\n"
    for cid, c in results:
        expire_date = datetime.strptime(c["expire"], "%Y-%m-%d")
        days_left = (expire_date - datetime.now()).days
        result += f"【{c['name']}】\n"
        result += f"  编号：{cid}\n"
        if c["type"] == "满减":
            result += f"  优惠：满{c['min_amount']}元减{c['value']}元\n"
        elif c["type"] == "折扣":
            result += f"  优惠：{100-c['value']}折\n"
        else:
            result += f"  优惠：免运费\n"
        result += f"  有效期：{c['expire']}（剩余{days_left}天）\n\n"

    result += "回复优惠券编号即可领取，如：C002"
    return result


@tool
async def get_points(user_id: str) -> str:
    """查询会员积分

    Args:
        user_id: 客户ID
    """
    points = POINTS.get(user_id, 0)
    level = VIP_LEVELS.get(user_id, "普通")

    # 计算等级权益
    benefits = []
    if points >= 10000:
        level_name = "钻石会员"
        benefits = ["全场9折", "每月专属礼包", "优先售后", "生日双倍积分"]
    elif points >= 5000:
        level_name = "金牌会员"
        benefits = ["全场95折", "每月礼包", "优先售后"]
    elif points >= 1000:
        level_name = "银牌会员"
        benefits = ["全场98折", "积分加倍"]
    else:
        level_name = "普通会员"
        benefits = ["积分可用于抵扣"]

    result = f"""会员信息：
━━━━━━━━━━━━━━━━━━━━━━━━━━
会员ID：{user_id}
会员等级：{level_name}（{level}）
当前积分：{points:,} 分

积分规则：
- 每消费1元累积1分
- 100积分可抵扣1元
- 生日当天双倍积分

等级权益："""
    for b in benefits:
        result += f"\n  • {b}"

    return result


@tool
async def redeem_points(user_id: str, points_to_redeem: int) -> str:
    """积分兑换

    Args:
        user_id: 客户ID
        points_to_redeem: 要兑换的积分数量（100积分=1元）
    """
    current_points = POINTS.get(user_id, 0)

    if points_to_redeem < 100:
        return "最低兑换100积分，请重新输入。"

    if points_to_redeem > current_points:
        return f"您的积分余额不足。当前剩余：{current_points}分"

    # 模拟兑换
    exchange_amount = points_to_redeem / 100
    POINTS[user_id] = current_points - points_to_redeem

    return f"""积分兑换成功！
━━━━━━━━━━━━━━━━━━━━━━━━━━
兑换积分：{points_to_redeem} 分
兑换金额：¥{exchange_amount:.2f}
剩余积分：{POINTS[user_id]} 分

兑换金额已存入您的账户，下次购物可直接使用。
感谢您的支持！"""
