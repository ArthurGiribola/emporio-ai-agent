"""Interactive multi-turn CLI with immutable startup identity and data scope."""

import argparse
from contextlib import ExitStack
from pathlib import Path

from app.agent import Agent
from app.data_session import open_tools
from app.policies import PolicyDataError
from app.providers import ConfigurationError, ProviderConfig, create_provider
from app.repository import DataValidationError


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
        with ExitStack() as stack:
            tools = stack.enter_context(open_tools(args.data_mode, data_dir=args.data_dir, policy_path=args.policy_path,
                enable_demo_identity=args.enable_demo_identity, demo_customer_id=args.demo_customer_id))
            if args.data_mode == "synthetic":
                output_fn("Synthetic data and policies; demo customer 1. Order 2 is not accessible.")
            else:
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
