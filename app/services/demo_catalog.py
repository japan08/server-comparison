from typing import TypedDict


class DemoRecommendation(TypedDict):
    provider: str
    instance: str
    vcpu: int
    ram: float
    price_monthly: float
    region: str
    country: str
    continent: str


DEMO_CATALOG: tuple[DemoRecommendation, ...] = (
    {
        "provider": "Hetzner",
        "instance": "CPX31",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 64.97,
        "region": "Falkenstein",
        "country": "Germany",
        "continent": "Europe",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 96.36,
        "region": "Frankfurt",
        "country": "Germany",
        "continent": "Europe",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 100.74,
        "region": "Bangalore",
        "country": "India",
        "continent": "Asia",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 105.12,
        "region": "San Francisco",
        "country": "USA",
        "continent": "North America",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-32gb",
        "vcpu": 4,
        "ram": 32.0,
        "price_monthly": 96.36,
        "region": "Singapore",
        "country": "Singapore",
        "continent": "Asia",
    },
)


def get_demo_recommendations(
    cpu: int,
    ram: float,
    budget: float,
    region: str,
) -> list[dict]:
    region_text = region.strip().lower()
    matches = []

    for item in DEMO_CATALOG:
        if item["vcpu"] < cpu or item["ram"] < ram or item["price_monthly"] > budget:
            continue
        search_blob = " ".join((item["continent"], item["country"], item["region"])).lower()
        if region_text and region_text not in search_blob:
            continue
        matches.append(
            {
                "provider": item["provider"],
                "instance": item["instance"],
                "vcpu": item["vcpu"],
                "ram": item["ram"],
                "price_monthly": item["price_monthly"],
            }
        )

    matches.sort(key=lambda recommendation: recommendation["price_monthly"])
    return matches[:3]
