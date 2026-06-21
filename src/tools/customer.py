"""
客户信息工具
"""

from langchain_core.tools import tool

# 模拟数据库
CUSTOMERS = {
    "user001": {
        "name": "张三",
        "level": "VIP",
        "phone": "138****3214",
        "email": "zhangsan@example.com",
        "address": "北京市朝阳区xxx",
        "balance": 999.50,
    },
    "user002": {
        "name": "李四",
        "level": "VIP",
        "phone": "139****5678",
        "email": "lisi@example.com",
        "address": "上海市浦东新区xxx",
        "balance": 0.00,
    },
    "user003": {
        "name": "王五",
        "level": "普通",
        "phone": "137****9012",
        "email": "wangwu@example.com",
        "address": "广州市天河区xxx",
        "balance": 100.00,
    },
}


@tool
async def get_customer_info(user_id: str) -> str:
    """获取客户信息

    Args:
        user_id: 客户ID，如 user001, user002, user003
    """
    customer = CUSTOMERS.get(user_id)

    if not customer:
        return f"未找到客户 {user_id} 的信息。请确认客户ID是否正确。"

    return f"""客户信息：
- 姓名：{customer['name']}
- 会员等级：{customer['level']}
- 电话：{customer['phone']}
- 邮箱：{customer['email']}
- 地址：{customer['address']}
- 账户余额：¥{customer['balance']:.2f}"""
