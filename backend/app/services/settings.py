import os
from pathlib import Path

from dotenv import set_key, unset_key

from app.core.config import Settings, get_settings
from app.schemas import RuntimeSettingsRead, RuntimeSettingsUpdate

SETTING_ENV_NAMES = {
    "test_logs_directory": "TRACEQA_TEST_LOGS_DIRECTORY",
    "llm_model": "TRACEQA_LLM_MODEL",
    "llm_api_base": "TRACEQA_LLM_API_BASE",
    "llm_api_key": "TRACEQA_LLM_API_KEY",
    "github_token": "TRACEQA_GITHUB_TOKEN",
    "github_webhook_secret": "TRACEQA_GITHUB_WEBHOOK_SECRET",
}


def serialize_runtime_settings(settings: Settings) -> RuntimeSettingsRead:
    return RuntimeSettingsRead(
        test_logs_directory=str(settings.test_logs_directory),
        llm_model=settings.llm_model,
        llm_api_base=settings.llm_api_base,
        llm_api_key_configured=bool(
            settings.llm_api_key
            and settings.llm_api_key.get_secret_value()
        ),
        github_token_configured=bool(
            settings.github_token
            and settings.github_token.get_secret_value()
        ),
        github_webhook_secret_configured=(
            bool(
                settings.github_webhook_secret
                and settings.github_webhook_secret.get_secret_value()
            )
        ),
    )


class RuntimeSettingsStore:
    def __init__(self, env_file: Path) -> None:
        self.env_file = env_file

    def read(self) -> RuntimeSettingsRead:
        return serialize_runtime_settings(get_settings())

    def update(self, payload: RuntimeSettingsUpdate) -> RuntimeSettingsRead:
        self.env_file.touch(exist_ok=True)
        for field, value in payload.model_dump(exclude_unset=True).items():
            env_name = SETTING_ENV_NAMES[field]
            if value == "":
                unset_key(str(self.env_file), env_name)
                os.environ.pop(env_name, None)
                continue
            if value is None:
                continue
            normalized = str(value)
            set_key(str(self.env_file), env_name, normalized, quote_mode="always")
            os.environ[env_name] = normalized

        get_settings.cache_clear()
        return serialize_runtime_settings(get_settings())
