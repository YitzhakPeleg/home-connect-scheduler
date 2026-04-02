import time

import httpx
import pytest
import respx

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.models import AppData, TokenData
from home_connect_scheduler.settings import settings


@pytest.fixture
def mock_api():
    with respx.mock(base_url=settings.api_base_url) as rsps:
        yield rsps


@pytest.fixture
def stored_tokens(tmp_path, monkeypatch):
    """Patch store to use tmp dir and pre-populate with valid tokens."""
    from unittest.mock import patch

    data_dir = tmp_path / ".hcs"
    data_file = data_dir / "data.json"

    with (
        patch("home_connect_scheduler.store.DATA_DIR", data_dir),
        patch("home_connect_scheduler.store.DATA_FILE", data_file),
        patch("home_connect_scheduler.homeconnect.load") as mock_load,
        patch("home_connect_scheduler.homeconnect.save") as mock_save,
    ):
        tokens = TokenData(
            access_token="valid-token",
            refresh_token="valid-refresh",
            expires_at=time.time() + 3600,
        )
        data = AppData(tokens=tokens)
        mock_load.return_value = data
        yield mock_load, mock_save


@pytest.fixture
def expired_tokens(tmp_path):
    from unittest.mock import patch

    data_dir = tmp_path / ".hcs"
    data_file = data_dir / "data.json"

    with (
        patch("home_connect_scheduler.store.DATA_DIR", data_dir),
        patch("home_connect_scheduler.store.DATA_FILE", data_file),
        patch("home_connect_scheduler.homeconnect.load") as mock_load,
        patch("home_connect_scheduler.homeconnect.save") as mock_save,
    ):
        tokens = TokenData(
            access_token="expired-token",
            refresh_token="valid-refresh",
            expires_at=time.time() - 100,
        )
        data = AppData(tokens=tokens)
        mock_load.return_value = data
        yield mock_load, mock_save


class TestTokenExchange:
    @pytest.mark.asyncio
    async def test_exchange_code(self, mock_api, tmp_path):
        from unittest.mock import patch

        data_dir = tmp_path / ".hcs"
        data_file = data_dir / "data.json"

        with (
            patch("home_connect_scheduler.store.DATA_DIR", data_dir),
            patch("home_connect_scheduler.store.DATA_FILE", data_file),
            patch("home_connect_scheduler.homeconnect.load") as mock_load,
            patch("home_connect_scheduler.homeconnect.save") as mock_save,
        ):
            mock_load.return_value = AppData()

            mock_api.post("/security/oauth/token").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "expires_in": 3600,
                    },
                )
            )

            client = HomeConnectClient()
            await client.exchange_code("auth-code")
            await client.close()

            mock_save.assert_called_once()
            saved_data = mock_save.call_args[0][0]
            assert saved_data.tokens.access_token == "new-access"


class TestTokenRefresh:
    @pytest.mark.asyncio
    async def test_auto_refresh_on_expired(self, mock_api, expired_tokens):
        _mock_load, mock_save = expired_tokens

        mock_api.post("/security/oauth/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "refreshed-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )
        )
        mock_api.get("/api/homeappliances").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"homeappliances": []}},
            )
        )

        client = HomeConnectClient()
        result = await client.list_appliances()
        await client.close()

        assert result == []
        mock_save.assert_called_once()


class TestListAppliances:
    @pytest.mark.asyncio
    async def test_success(self, mock_api, stored_tokens):
        appliances = [
            {"haId": "BOSCH-123", "type": "Dishwasher", "name": "My Dishwasher", "brand": "Bosch"}
        ]
        mock_api.get("/api/homeappliances").mock(
            return_value=httpx.Response(200, json={"data": {"homeappliances": appliances}})
        )

        client = HomeConnectClient()
        result = await client.list_appliances()
        await client.close()

        assert len(result) == 1
        assert result[0]["haId"] == "BOSCH-123"


class TestStartProgram:
    @pytest.mark.asyncio
    async def test_success(self, mock_api, stored_tokens):
        mock_api.put("/api/homeappliances/BOSCH-123/programs/active").mock(
            return_value=httpx.Response(204)
        )

        client = HomeConnectClient()
        await client.start_program("BOSCH-123", "Dishcare.Program.Eco50")
        await client.close()

    @pytest.mark.asyncio
    async def test_409_not_ready(self, mock_api, stored_tokens):
        mock_api.put("/api/homeappliances/BOSCH-123/programs/active").mock(
            return_value=httpx.Response(409, json={"error": "not ready"})
        )

        client = HomeConnectClient()
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.start_program("BOSCH-123", "Dishcare.Program.Eco50")
        assert exc_info.value.response.status_code == 409
        await client.close()


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_success(self, mock_api, stored_tokens):
        status = [
            {
                "key": "BSH.Common.Status.OperationState",
                "value": "BSH.Common.EnumType.OperationState.Run",
            },
            {
                "key": "BSH.Common.Status.DoorState",
                "value": "BSH.Common.EnumType.DoorState.Closed",
            },
        ]
        mock_api.get("/api/homeappliances/BOSCH-123/status").mock(
            return_value=httpx.Response(200, json={"data": {"status": status}})
        )

        client = HomeConnectClient()
        result = await client.get_status("BOSCH-123")
        await client.close()

        assert len(result) == 2
        assert result[0]["key"] == "BSH.Common.Status.OperationState"


class TestTokenParams:
    @pytest.mark.asyncio
    async def test_includes_secret_when_set(self, stored_tokens):
        from unittest.mock import patch

        with patch("home_connect_scheduler.homeconnect.settings") as mock_settings:
            mock_settings.client_id = "test-id"
            mock_settings.client_secret = "test-secret"
            client = HomeConnectClient()
            params = client._token_params(grant_type="authorization_code")
            assert params["client_secret"] == "test-secret"
            assert params["client_id"] == "test-id"
            await client.close()

    @pytest.mark.asyncio
    async def test_omits_secret_when_empty(self, stored_tokens):
        from unittest.mock import patch

        with patch("home_connect_scheduler.homeconnect.settings") as mock_settings:
            mock_settings.client_id = "test-id"
            mock_settings.client_secret = ""
            client = HomeConnectClient()
            params = client._token_params(grant_type="authorization_code")
            assert "client_secret" not in params
            await client.close()


class TestListPrograms:
    @pytest.mark.asyncio
    async def test_success(self, mock_api, stored_tokens):
        programs = [{"key": "Dishcare.Program.Eco50"}, {"key": "Dishcare.Program.Auto2"}]
        mock_api.get("/api/homeappliances/BOSCH-123/programs/available").mock(
            return_value=httpx.Response(200, json={"data": {"programs": programs}})
        )

        client = HomeConnectClient()
        result = await client.list_programs("BOSCH-123")
        await client.close()

        assert len(result) == 2
