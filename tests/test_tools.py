"""
工具模块测试
"""

import asyncio


def test_customer_info():
    """测试客户信息查询"""
    from src.tools.customer import get_customer_info

    result = asyncio.run(get_customer_info.ainvoke({"user_id": "user001"}))
    assert "张三" in result
    print("[PASS] customer info test")


def test_order_query():
    """测试订单查询"""
    from src.tools.order import query_orders

    result = asyncio.run(query_orders.ainvoke({"user_id": "user001"}))
    assert "user001" in result or "暂无订单" in result
    print("[PASS] order query test")


def test_knowledge_search():
    """测试知识库搜索"""
    from src.tools.knowledge import search_knowledge_base

    result = asyncio.run(search_knowledge_base.ainvoke({"keyword": "退货"}))
    assert "退货" in result or "未找到" in result
    print("[PASS] knowledge search test")


if __name__ == "__main__":
    test_customer_info()
    test_order_query()
    test_knowledge_search()
    print("\n=== All tool tests passed ===")
