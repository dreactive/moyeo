"""External, structured-only LangChain adapter. Credentials are checked on use."""
import json
import os
from pathlib import Path
from threading import Lock
from ai.auxiliary_schema import AuxiliaryBatch


class AuxiliaryConfigurationError(RuntimeError):
    pass


class AuxiliaryServiceError(RuntimeError):
    pass


def auxiliary_settings(config):
    names = ('OPENAI_API_KEY', 'AUX_API_KEY', 'AUX_BASE_URL', 'AUX_MODEL', 'AUX_REASONING_EFFORT')
    values = {}
    path = Path(config.get('env_file') or '')
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = line.removeprefix('export ').partition('=')
            if separator and key.strip() in names:
                values[key.strip()] = value.strip().strip('\"').strip("'")
    values.update({name: os.environ[name] for name in names if os.environ.get(name)})
    return dict(api_key=config.get('aux_api_key') or values.get('OPENAI_API_KEY') or values.get('AUX_API_KEY'),
                base_url=config.get('aux_base_url') or values.get('AUX_BASE_URL') or None,
                model=config.get('aux_model') or values.get('AUX_MODEL') or 'gpt-6-luna',
                reasoning_effort=config.get('aux_reasoning_effort') or values.get('AUX_REASONING_EFFORT') or 'none')


class ExternalAuxiliary:
    backend = 'external'

    def __init__(self, config):
        values = auxiliary_settings(config)
        self._api_key, self.base_url, self.model = values['api_key'], values['base_url'], values['model']
        self.reasoning_effort = values['reasoning_effort']
        self._structured = None
        self._lock = Lock()

    def _client(self):
        if not self._api_key:
            raise AuxiliaryConfigurationError('External auxiliary requires OPENAI_API_KEY.')
        if not self.model:
            raise AuxiliaryConfigurationError('External auxiliary requires AUX_MODEL.')
        with self._lock:
            if self._structured is None:
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise AuxiliaryConfigurationError('External auxiliary requires langchain-openai.') from None
                try:
                    client = ChatOpenAI(model=self.model, api_key=self._api_key, base_url=self.base_url,
                                        timeout=45, max_retries=0, reasoning_effort=self.reasoning_effort)
                    self._structured = client.with_structured_output(AuxiliaryBatch, method='json_schema', strict=True)
                except Exception:
                    raise AuxiliaryConfigurationError('Unable to initialize external auxiliary.') from None
        return self._structured

    def extract(self, task: dict, stage: int = 1) -> dict:
        if stage not in (1, 2):
            raise ValueError('Auxiliary stage must be 1 or 2.')
        client = self._client()
        prompt = Path(__file__).with_name('prompts').joinpath('auxiliary.txt').read_text(encoding='utf-8')
        try:
            result = client.invoke([('system', prompt), ('human', json.dumps(dict(stage=stage, task=task), ensure_ascii=False))])
            return AuxiliaryBatch.model_validate(result.model_dump() if isinstance(result, AuxiliaryBatch) else result).model_dump()
        except Exception:
            raise AuxiliaryServiceError('External auxiliary request or structured validation failed.') from None
