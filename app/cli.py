"""Interactive multi-turn CLI with immutable startup identity and data scope."""

import argparse
from contextlib import ExitStack
from pathlib import Path

from app.agent import Agent
from app.orders import DemoSessionConfig, OrderService
from app.policies import PolicyDataError, PolicyRetriever
from app.providers import ConfigurationError, ProviderConfig, create_provider
from app.repository import DataValidationError, Repository
from app.synthetic import SyntheticTools
from app.tool_runtime import ToolRuntime


def main(argv=None, *, input_fn=input, output_fn=print, provider_factory=create_provider):
    parser = argparse.ArgumentParser(description="Music-store AI customer service")
    parser.add_argument("--data-mode", choices=("synthetic", "local"), default="synthetic")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--policy-path", type=Path)
    parser.add_argument("--enable-demo-identity", action="store_true")
    parser.add_argument("--demo-customer-id", type=int)
    args = parser.parse_args(argv)
    try:
        config = ProviderConfig.from_environment()
        if config.provider == "gemini" and args.data_mode != "synthetic":
            raise ConfigurationError("Gemini cannot use supplied store files; choose Ollama for local data")
        if args.data_mode == "synthetic" and (args.enable_demo_identity or args.demo_customer_id is not None or args.policy_path is not None or args.data_dir != Path("data")):
            raise ConfigurationError("Synthetic mode uses only approved fixtures and its fixed demo identity; custom data/identity options are not accepted")
        with ExitStack() as stack:
            if args.data_mode == "synthetic":
                tools = stack.enter_context(SyntheticTools())
                output_fn("Synthetic data and policies; demo customer 1. Order 2 is not accessible.")
            else:
                repository = Repository(args.data_dir)
                policy = PolicyRetriever(args.policy_path or args.data_dir / "políticas_da_loja.pdf")
                orders = OrderService(repository, DemoSessionConfig(args.enable_demo_identity, args.demo_customer_id))
                tools = ToolRuntime(repository, policy, orders)
                output_fn("Local snapshot data. Demo identity is not production authentication; it cannot change in chat.")
            agent = Agent(provider_factory(config), tools)
            output_fn("Enter arbitrary shop questions. /reset clears history; /quit exits. No transcript is saved.")
            if config.provider == "gemini":
                output_fn("Gemini receives approved synthetic data and filtered demo vocabulary, never your original free-form text. Do not enter personal information.")
            while True:
                try:
                    question = input_fn("You: ")
                except (EOFError, KeyboardInterrupt):
                    output_fn("Session ended.")
                    break
                if question.strip().casefold() == "/quit":
                    break
                if question.strip().casefold() == "/reset":
                    agent.reset()
                    output_fn("Conversation cleared; identity unchanged.")
                    continue
                result = agent.run(question)
                output_fn("Assistant: " + result.text)
                if result.status != "answered":
                    output_fn("Status: " + result.status)
            return 0
    except KeyboardInterrupt:
        output_fn("Session interrupted.")
        return 130
    except (ConfigurationError, DataValidationError, PolicyDataError, ValueError, OSError) as error:
        output_fn("Startup error: " + str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
