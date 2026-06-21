"""
工具模块
"""
from .customer import get_customer_info
from .order import query_orders, get_order_status
from .knowledge import search_knowledge_base
from .escalation import create_ticket, transfer_to_human
from .product import search_products, get_product_detail, check_stock, get_recommendations
from .marketing import search_coupons, get_points, redeem_points
from .order_ops import track_delivery, cancel_order, apply_refund, modify_address
from .invoice import query_invoice, apply_invoice

__all__ = [
    # 客户服务
    "get_customer_info",
    # 订单查询
    "query_orders",
    "get_order_status",
    # 知识库
    "search_knowledge_base",
    # 升级转接
    "create_ticket",
    "transfer_to_human",
    # 商品服务
    "search_products",
    "get_product_detail",
    "check_stock",
    "get_recommendations",
    # 营销服务
    "search_coupons",
    "get_points",
    "redeem_points",
    # 订单操作
    "track_delivery",
    "cancel_order",
    "apply_refund",
    "modify_address",
    # 发票服务
    "query_invoice",
    "apply_invoice",
]
