"""
商品相关工具
"""

from langchain_core.tools import tool
from typing import Optional, List

# 模拟商品数据库
PRODUCTS = {
    "iphone15": {
        "id": "P001",
        "name": "iPhone 15 Pro 256G 钛金色",
        "price": 8999.00,
        "stock": 50,
        "category": "手机",
        "description": "A17 Pro芯片，钛金属设计，4800万像素主摄"
    },
    "airpods": {
        "id": "P002",
        "name": "AirPods Pro 2",
        "price": 1899.00,
        "stock": 200,
        "category": "耳机",
        "description": "主动降噪，空间音频，无线充电"
    },
    "macbook": {
        "id": "P003",
        "name": "MacBook Pro 14寸 M3",
        "price": 14999.00,
        "stock": 30,
        "category": "电脑",
        "description": "M3芯片，14.2英寸Liquid视网膜XDR屏"
    },
    "ipad": {
        "id": "P004",
        "name": "iPad Air 5 64G WiFi",
        "price": 4399.00,
        "stock": 100,
        "category": "平板",
        "description": "M1芯片，10.9英寸全面屏"
    },
    "watch": {
        "id": "P005",
        "name": "Apple Watch S9",
        "price": 3299.00,
        "stock": 150,
        "category": "手表",
        "description": "S9芯片，血氧检测，心电图功能"
    },
}


@tool
async def search_products(
    keyword: str,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    sort_by: str = "relevance"
) -> str:
    """搜索商品

    Args:
        keyword: 搜索关键词，如"手机"、"苹果"、"iPhone"
        category: 商品分类筛选，可选：手机/电脑/平板/耳机/手表
        max_price: 最高价格筛选
        sort_by: 排序方式，可选：relevance(相关性)/price_asc(价格升序)/price_desc(价格降序)/stock(库存)
    """
    results = []

    # 搜索匹配
    for pid, product in PRODUCTS.items():
        # 关键词匹配
        if keyword.lower() in product["name"].lower() or keyword.lower() in product["description"].lower():
            # 分类筛选
            if category and product["category"] != category:
                continue
            # 价格筛选
            if max_price and product["price"] > max_price:
                continue
            results.append(product)

    # 排序
    if sort_by == "price_asc":
        results.sort(key=lambda x: x["price"])
    elif sort_by == "price_desc":
        results.sort(key=lambda x: x["price"], reverse=True)
    elif sort_by == "stock":
        results.sort(key=lambda x: x["stock"], reverse=True)

    if not results:
        return f"未找到包含「{keyword}」的商品，请尝试其他关键词。"

    result = f"找到 {len(results)} 件商品：\n\n"
    for i, p in enumerate(results[:10], 1):
        stock_status = "有货" if p["stock"] > 0 else "缺货"
        result += f"{i}. {p['name']}\n"
        result += f"   价格：¥{p['price']:.2f} | 库存：{stock_status}\n"
        result += f"   分类：{p['category']} | 编号：{p['id']}\n"
        result += f"   简介：{p['description']}\n\n"

    return result


@tool
async def get_product_detail(product_id: str) -> str:
    """查询商品详情

    Args:
        product_id: 商品编号，如 P001、P002
    """
    for pid, product in PRODUCTS.items():
        if product["id"] == product_id:
            stock_status = "有货" if product["stock"] > 0 else "缺货"
            return f"""商品详情：
━━━━━━━━━━━━━━━━━━━━━━━━━━
商品编号：{product['id']}
商品名称：{product['name']}
价格：¥{product['price']:.2f}
库存：{stock_status}（{product['stock']}件）
分类：{product['category']}

商品介绍：
{product['description']}

购买提示：
- 支持分期付款（3/6/12期免息）
- 全国联保一年
- 7天无理由退货（激活后不支持）"""

    return f"未找到编号为 {product_id} 的商品"


@tool
async def check_stock(product_id: str) -> str:
    """查询商品库存

    Args:
        product_id: 商品编号
    """
    for pid, product in PRODUCTS.items():
        if product["id"] == product_id:
            if product["stock"] == 0:
                return f"商品「{product['name']}」（编号：{product['id']}）当前缺货，\n预计3-5个工作日后到货。\n您可以：\n1. 留下联系方式，到货后通知您\n2. 查看同类商品推荐"
            elif product["stock"] < 10:
                return f"商品「{product['name']}」（编号：{product['id']}）库存紧张！\n剩余：{product['stock']}件\n建议尽快下单。"
            else:
                return f"商品「{product['name']}」（编号：{product['id']}）库存充足。\n剩余：{product['stock']}件"

    return f"未找到编号为 {product_id} 的商品"


@tool
async def get_recommendations(user_id: str, category: Optional[str] = None, limit: int = 3) -> str:
    """根据用户历史和偏好推荐商品

    Args:
        user_id: 客户ID
        category: 指定分类，可选
        limit: 返回数量，默认3个
    """
    # 模拟推荐逻辑
    recommendations = []

    if category:
        filtered = [p for p in PRODUCTS.values() if p["category"] == category]
        recommendations = filtered[:limit]
    else:
        # 热门推荐
        popular = sorted(PRODUCTS.values(), key=lambda x: x["stock"], reverse=True)
        recommendations = popular[:limit]

    if not recommendations:
        return "暂无推荐商品"

    result = f"为您推荐 {len(recommendations)} 件商品：\n\n"
    for i, p in enumerate(recommendations, 1):
        result += f"{i}. {p['name']} - ¥{p['price']:.2f}\n"
        result += f"   {p['description']}\n\n"

    result += "回复商品编号可查看详情，如：P001"

    return result
