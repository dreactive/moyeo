import os
from pathlib import Path
from dotenv import dotenv_values


def read_settings(env_file=None):
    path = Path(env_file or os.environ.get('TRIP_ENV_FILE', '.env')).resolve()
    values = dict(dotenv_values(path)) if path.is_file() else {}
    values.update(os.environ)
    mode = values.get('AGENT_MODE', 'fixture')
    if mode not in ('fixture','local_ai'):
        raise ValueError('Unknown AGENT_MODE')
    return {
        'database_path':values.get('BACKEND_DB','backend/.data/travel.sqlite3'),
        'dev_token':values.get('DEV_TOKEN',''),
        'agent_mode':mode,
        'public_map_key':values.get('KAKAO_JAVASCRIPT_KEY',''),
        'trace_enabled':values.get('TRACE_ENABLED','1') != '0',
        'runtime_config':{
            'model_backend':values.get('MODEL_BACKEND','fake'),
            'provider_mode':values.get('PROVIDER_MODE','fixture'),
            'base_model_path':values.get('BASE_MODEL_PATH'),
            'adapter_path':values.get('ADAPTER_PATH'),
            'env_file':str(path),
        },
    }
