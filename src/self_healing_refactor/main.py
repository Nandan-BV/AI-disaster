import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from .graph.builder import build_refactor_graph, create_initial_state


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Self-Healing Codebase Refactoring Engine")
    parser.add_argument("repository_path", help="Path to the Python repository to refactor")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts (default: 3)")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")

    args = parser.parse_args()

    if args.api_key:
        os.environ["OPENAI_API_KEY"] = args.api_key
    elif not os.getenv("OPENAI_API_KEY"):
        print("Error: OpenAI API key required. Set OPENAI_API_KEY env var or use --api-key")
        return 1

    repo_path = Path(args.repository_path).resolve()
    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}")
        return 1

    print(f"Starting self-healing refactoring on: {repo_path}")
    print(f"Max retries: {args.max_retries}")

    graph = build_refactor_graph(max_retries=args.max_retries)
    initial_state = create_initial_state(str(repo_path), max_retries=args.max_retries)

    try:
        final_state = graph.invoke(initial_state)
        test_results = final_state.get("test_results", {})
        return_code = test_results.get("return_code", 1)
        retry_count = final_state.get("retry_count", 0)

        if return_code == 0:
            print(f"\n✅ Success! All tests passed after {retry_count} attempt(s).")
            return 0
        else:
            print(f"\n❌ Failed after {retry_count} attempt(s). Max retries reached.")
            return 1
    except Exception as e:
        print(f"\n💥 Error during refactoring: {e}")
        return 1


if __name__ == "__main__":
    exit(main())