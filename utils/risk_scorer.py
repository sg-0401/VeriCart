from utils.order_db import get_customer, get_customer_for_order


def compute_risk_score(customer_id=None, order_id=None):
    customer = get_customer(customer_id) if customer_id else get_customer_for_order(order_id)
    if not customer:
        return {"score": 5.0, "level": "Medium", "details": "Customer not found"}
    age = customer.get("account_age_days", 0)
    returns = customer.get("past_returns", 0)
    flags = customer.get("fraud_flags", 0)
    score = 0
    score += 3 if age < 30 else 2.5 if age < 90 else 2 if age < 180 else 1.5 if age < 365 else .5 if age < 730 else 0
    score += 0 if returns == 0 else 1 if returns <= 2 else 2.5 if returns <= 5 else 3.5 if returns <= 8 else 4
    score += min(flags * 1.5, 4.5)
    score = min(10.0, score)
    level = "Low" if score <= 3 else "Medium" if score <= 6 else "High"
    return {"score": round(score,2), "level": level, "customer_name": customer.get("name", "Unknown"),
            "account_age_days": age, "past_returns": returns, "fraud_flags": flags}
