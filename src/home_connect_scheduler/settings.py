from functools import cached_property

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    client_id: str
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080"
    use_simulator: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @cached_property
    def api_base_url(self) -> str:
        if self.use_simulator:
            return "https://simulator.home-connect.com"
        return "https://api.home-connect.com"


settings = Settings()  # type: ignore[call-arg]
