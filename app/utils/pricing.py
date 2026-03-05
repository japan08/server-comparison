def hourly_to_monthly(hourly_price: float) -> float:
    return hourly_price * 730


def calculate_price_score(price: float, cheapest_price: float) -> float:
    if price <= 0:
        return 0.0
    return cheapest_price / price
