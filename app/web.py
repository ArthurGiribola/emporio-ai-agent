"""Fixed loopback-only Streamlit launcher; the CLI remains independent."""

import sys
from pathlib import Path


def main():
    try:
        from streamlit.web import cli
    except ImportError:
        raise SystemExit('Install the optional interface first: python -m pip install -e ".[ui]"') from None
    sys.argv = ["streamlit", "run", str(Path(__file__).with_name("streamlit_app.py")),
                "--server.address=127.0.0.1", "--server.port=8501", "--server.headless=true",
                "--browser.gatherUsageStats=false", "--client.showErrorDetails=none",
                "--server.fileWatcherType=none"]
    return cli.main()


if __name__ == "__main__":
    main()
