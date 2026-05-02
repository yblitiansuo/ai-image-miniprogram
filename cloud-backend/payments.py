from datetime import datetime, timezone

# 套餐配置
PACKAGES = [
    {"id": "free_trial", "name": "免费试用", "quota": 1, "price": 0.0, "description": "新用户免费生成 1 次"},
    {"id": "basic_10", "name": "基础包", "quota": 10, "price": 9.9, "description": "10 次生成配额"},
    {"id": "pro_50", "name": "专业包", "quota": 50, "price": 39.9, "description": "50 次生成配额，性价比高"},
    {"id": "unlimited_monthly", "name": "无限月卡", "quota": -1, "price": 199.0, "description": "30 天内无限生成"},
]

def get_packages() -> list:
    return PACKAGES

def create_order(user_id: str, package_id: str):
    from models import SessionLocal, Order, OrderStatus
    db = SessionLocal()
    try:
        pkg = next((p for p in PACKAGES if p["id"] == package_id), None)
        if not pkg:
            raise ValueError("套餐不存在")
        order = Order(
            user_id=user_id,
            package_id=package_id,
            package_name=pkg["name"],
            quota_added=pkg["quota"],
            price=pkg["price"],
            status=OrderStatus.pending
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order
    finally:
        db.close()

def complete_order(order_id: str, wechat_tx_id: str = None):
    from models import SessionLocal, Order, OrderStatus, User
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order or order.status != OrderStatus.pending:
            return None
        order.status = OrderStatus.paid
        order.wechat_transaction_id = wechat_tx_id
        order.paid_at = datetime.now(timezone.utc)
        db.commit()
        user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
        if user:
            if order.quota_added == -1:
                user.quota = 999999  # 无限月卡
            elif order.quota_added > 0:
                user.quota += order.quota_added
            db.commit()
        return order
    finally:
        db.close()
