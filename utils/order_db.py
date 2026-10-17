"""Demo order catalogue used by VeriCart.

Replace this module with a real database/repository in production.  The demo
catalogue deliberately stores variant information because a wrong colour,
model, or size is a different grievance from physical damage.
"""

ORDERS = {
    "ORD001": {
        "order_id": "ORD001", "product": "Sony WH-1000XM5 Headphones",
        "category": "Electronics", "brand": "Sony", "model": "WH-1000XM5",
        "color": "Black", "size": None, "price": 29999, "customer_id": "CUST001",
        "date": "2026-07-15", "status": "Delivered", "reference_image": "Sony WH-1000XM5 Headphones.jpg"
    },
    "ORD002": {
        "order_id": "ORD002", "product": "Nike Air Zoom Running Shoes",
        "category": "Footwear", "brand": "Nike", "model": "Air Zoom",
        "color": "Black/White", "size": "9", "price": 7499, "customer_id": "CUST002",
        "date": "2026-07-20", "status": "Delivered", "reference_image": None
    },
    "ORD003": {
        "order_id": "ORD003", "product": "Levi's 511 Slim Fit Jeans",
        "category": "Clothing", "brand": "Levi's", "model": "511 Slim Fit",
        "color": "Blue", "size": "32", "price": 2499, "customer_id": "CUST003",
        "date": "2026-08-01", "status": "Delivered", "reference_image": "Levi's 511 Slim Fit Jeans.jpg"
    },
    "ORD004": {
        "order_id": "ORD004", "product": "Apple Watch Series 9",
        "category": "Electronics", "brand": "Apple", "model": "Watch Series 9",
        "color": "Midnight", "size": "45mm", "price": 41900, "customer_id": "CUST004",
        "date": "2026-07-10", "status": "Delivered", "reference_image": "Apple Watch Series 9.jpg"
    },
    "ORD005": {
        "order_id": "ORD005", "product": "Tan Leather Crossbody Bag",
        "category": "Accessories", "brand": "", "model": "Crossbody Bag",
        "color": "Tan", "size": None, "price": 3299, "customer_id": "CUST005",
        "date": "2026-08-05", "status": "Delivered", "reference_image": None
    },
    "ORD006": {
        "order_id": "ORD006", "product": "Instant Pot Duo 7-in-1",
        "category": "Home & Kitchen", "brand": "Instant Pot", "model": "Duo 7-in-1",
        "color": "Black", "size": None, "price": 8999, "customer_id": "CUST001",
        "date": "2026-07-28", "status": "Delivered", "reference_image": None
    },
    "ORD007": {
        "order_id": "ORD007", "product": "Adidas Ultraboost 23",
        "category": "Footwear", "brand": "Adidas", "model": "Ultraboost 23",
        "color": "Black", "size": "9", "price": 12999, "customer_id": "CUST006",
        "date": "2026-08-03", "status": "Delivered", "reference_image": None
    },
    "ORD008": {
        "order_id": "ORD008", "product": "Samsung Galaxy S24 Ultra",
        "category": "Electronics", "brand": "Samsung", "model": "Galaxy S24 Ultra",
        "color": "Titanium Gray", "size": None, "price": 129999, "customer_id": "CUST007",
        "date": "2026-07-05", "status": "Delivered", "reference_image": None
    },
    "ORD009": {
        "order_id": "ORD009", "product": "Fossil Gen 6 Smartwatch",
        "category": "Electronics", "brand": "Fossil", "model": "Gen 6",
        "color": "Black", "size": None, "price": 22995, "customer_id": "CUST008",
        "date": "2026-08-07", "status": "Delivered", "reference_image": None
    },
    "ORD010": {
        "order_id": "ORD010", "product": "Puma Men's Polo T-Shirt",
        "category": "Clothing", "brand": "Puma", "model": "Polo T-Shirt",
        "color": "Black", "size": "M", "price": 1299, "customer_id": "CUST009",
        "date": "2026-08-09", "status": "Delivered", "reference_image": None
    },
}

CUSTOMERS = {
    "CUST001": {"name": "Arjun Sharma", "email": "arjun@example.com", "account_age_days": 730, "past_returns": 2, "fraud_flags": 0},
    "CUST002": {"name": "Priya Patel", "email": "priya@example.com", "account_age_days": 365, "past_returns": 1, "fraud_flags": 0},
    "CUST003": {"name": "Ravi Kumar", "email": "ravi@example.com", "account_age_days": 180, "past_returns": 5, "fraud_flags": 1},
    "CUST004": {"name": "Sneha Reddy", "email": "sneha@example.com", "account_age_days": 1095, "past_returns": 0, "fraud_flags": 0},
    "CUST005": {"name": "Vikram Singh", "email": "vikram@example.com", "account_age_days": 60, "past_returns": 3, "fraud_flags": 0},
    "CUST006": {"name": "Ananya Iyer", "email": "ananya@example.com", "account_age_days": 420, "past_returns": 1, "fraud_flags": 0},
    "CUST007": {"name": "Karan Mehta", "email": "karan@example.com", "account_age_days": 30, "past_returns": 8, "fraud_flags": 2},
    "CUST008": {"name": "Divya Nair", "email": "divya@example.com", "account_age_days": 500, "past_returns": 2, "fraud_flags": 0},
    "CUST009": {"name": "Rohit Joshi", "email": "rohit@example.com", "account_age_days": 240, "past_returns": 4, "fraud_flags": 1},
}


def get_order(order_id):
    return ORDERS.get((order_id or "").strip().upper())


def get_customer(customer_id):
    return CUSTOMERS.get(customer_id)


def get_customer_for_order(order_id):
    order = get_order(order_id)
    return get_customer(order["customer_id"]) if order else None
