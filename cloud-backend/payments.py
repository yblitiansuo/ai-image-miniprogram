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
        # 防重复下单：如果已有同套餐的未支付订单，直接返回
        existing = db.query(Order).filter(
            Order.user_id == user_id,
            Order.package_id == package_id,
            Order.status == OrderStatus.pending
        ).first()
        if existing:
            return {
                "id": existing.id,
                "package_name": existing.package_name,
                "price": existing.price,
                "quota_added": existing.quota_added,
                "status": existing.status.value,
            }

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
        return {
            "id": order.id,
            "package_name": order.package_name,
            "price": order.price,
            "quota_added": order.quota_added,
            "status": order.status.value,
        }
    finally:
        db.close()

def complete_order(order_id: str, wechat_tx_id: str = None, current_user_id: str = None):
    from models import SessionLocal, Order, OrderStatus, User
    db = SessionLocal()
    try:
        # 对 Order 加行锁，防止并发重复完成
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if not order or order.status != OrderStatus.pending:
            return None
        # 验证订单归属
        if current_user_id and order.user_id != current_user_id:
            return None
        order.status = OrderStatus.paid
        order.wechat_transaction_id = wechat_tx_id
        order.paid_at = datetime.now(timezone.utc)
        user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
        if user:
            if order.quota_added == -1:
                user.quota = 999999  # 无限月卡
            elif order.quota_added > 0:
                user.quota += order.quota_added
        db.commit()
        # 返回 dict，避免 session 关闭后 ORM 对象 DetachedInstanceError
        return {
            "id": order.id,
            "quota_added": order.quota_added,
            "status": order.status.value,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
