import httpx

USER_AGENT = "weather-aware-truck-routing/1.0"


def client(timeout: float = 20.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
