TABLE_SCHEMA = {
    "orders": {
        "description": "订单主表",
        "columns": {
            "order_id": {"type": "VARCHAR", "desc": "订单ID"},
            "user_id": {"type": "VARCHAR", "desc": "用户ID"},
            "amount": {"type": "DECIMAL", "desc": "订单金额"},
            "status": {"type": "VARCHAR", "desc": "订单状态(pending/completed/cancelled)"},
            "created_at": {"type": "TIMESTAMP", "desc": "创建时间"},
            "city": {"type": "VARCHAR", "desc": "下单城市"},
        }
    },
    "users": {
        "description": "用户表",
        "columns": {
            "user_id": {"type": "VARCHAR", "desc": "用户ID"},
            "username": {"type": "VARCHAR", "desc": "用户名"},
            "register_at": {"type": "TIMESTAMP", "desc": "注册时间"},
            "tier": {"type": "VARCHAR", "desc": "用户等级(free/pro/vip)"},
        }
    },
    "products": {
        "description": "商品表",
        "columns": {
            "product_id": {"type": "VARCHAR", "desc": "商品ID"},
            "name": {"type": "VARCHAR", "desc": "商品名"},
            "category": {"type": "VARCHAR", "desc": "类目"},
            "price": {"type": "DECIMAL", "desc": "价格"},
        }
    }
}


# 语义 → 表名的简单映射（实际项目可用向量检索）
TABLE_CATALOG = {
    "orders": "订单表，记录用户的购买订单，包含金额、状态、时间",
    "order_items": "订单明细表，记录每个订单的商品行项目",
    "users": "用户表，存储用户基本信息和注册时间",
    "products": "商品表，存储商品名称、类别、价格",
    "categories": "商品分类表，商品的层级分类",
    "payments": "支付流水表，记录支付方式和支付状态",
    "logistics": "物流表，记录配送状态和收货地址",
    "reviews": "评价表，用户对订单商品的评分和评论",
    "promotions": "促销活动表，优惠券和折扣规则",
    "user_behavior": "用户行为日志，点击、浏览、加购事件",
}
