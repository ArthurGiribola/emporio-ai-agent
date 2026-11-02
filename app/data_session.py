"""Shared CLI/UI construction of existing read-only data services."""

from contextlib import contextmanager
from pathlib import Path

from app.orders import DemoSessionConfig, OrderService
from app.policies import PolicyRetriever
from app.providers import ConfigurationError
from app.repository import Repository
from app.synthetic import SyntheticTools
from app.tool_runtime import ToolRuntime


@contextmanager
def open_tools(data_mode, *, data_dir=Path('data'), policy_path=None,
               enable_demo_identity=False, demo_customer_id=None):
    if data_mode == 'synthetic':
        if enable_demo_identity or demo_customer_id is not None or policy_path is not None or Path(data_dir) != Path('data'):
            raise ConfigurationError('Synthetic mode uses approved fixtures and its fixed identity only')
        with SyntheticTools() as tools:
            yield tools
    elif data_mode == 'local':
        repository = Repository(data_dir)
        policies = PolicyRetriever(policy_path or Path(data_dir) / 'políticas_da_loja.pdf')
        orders = OrderService(repository, DemoSessionConfig(enable_demo_identity, demo_customer_id))
        yield ToolRuntime(repository, policies, orders)
    else:
        raise ConfigurationError('Unknown data mode')
