"""Fixed synthetic provider smoke runner, not the final conversational CLI."""

import argparse

from app.agent import Agent
from app.providers import ConfigurationError, ProviderConfig, create_provider
from app.synthetic import QUESTIONS, SyntheticTools


def main():
    parser = argparse.ArgumentParser(description="Run a synthetic-only, no-paid-API provider demo")
    parser.add_argument("--scenario", choices=tuple(QUESTIONS), default="price")
    arguments = parser.parse_args()
    try:
        provider = create_provider(ProviderConfig.from_environment())
        with SyntheticTools() as tools:
            result = Agent(provider, tools).run(QUESTIONS[arguments.scenario])
        print("Synthetic demonstration; not actual customer data or store policy.")
        print(result.status + ": " + result.text)
        return 0 if result.status == "answered" else 1
    except ConfigurationError as error:
        print("Configuration error: " + str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
