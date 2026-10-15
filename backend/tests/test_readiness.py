import asyncio
import httpx
import pytest
from src.cli.check_demo import check_forecast


@pytest.mark.parametrize("recover", [True, False])
def test_weather_readiness_recovers_once_or_fails_explicitly(recover):
    requests = []
    def transport(request):
        requests.append(request)
        if not recover or len(requests) == 1: raise httpx.ConnectTimeout("Simulated provider failure")
        return httpx.Response(200, json={"daily": {"time": ["day"] * 4}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            if recover: await check_forecast(client, retry_delay=0)
            else:
                with pytest.raises(RuntimeError, match="two attempts"): await check_forecast(client, retry_delay=0)
    asyncio.run(run())
    assert len(requests) == 2
