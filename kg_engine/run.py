#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
knowledge-graph CLI - Standalone Version
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_script(script_name: str, args):
    """Run a script"""
    scripts_dir = Path(__file__).parent / 'scripts'
    script_path = scripts_dir / f"{script_name}.py"

    if not script_path.exists():
        print(f"[ERROR] Script not found: {script_name}", file=sys.stderr)
        return 1

    # Build command
    cmd = [sys.executable, str(script_path)]

    # Add arguments
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            cwd=Path(__file__).parent
        )
        return result.returncode
    except Exception as e:
        print(f"[ERROR] Script execution failed: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog='knowledge-graph',
        description='Knowledge Graph - Ontology v2.0 with entity recognition, relation extraction, graph query and visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  knowledge-graph build_index
  knowledge-graph ontology_cli --help
  knowledge-graph visualize_graph --output graph.html
        """
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # build_index
    subparsers.add_parser('build_index', help='Build vector index for semantic search')

    # knowledge_completer
    subparsers.add_parser('knowledge_completer', help='Knowledge completer for auto-completion')

    # ontology_cli
    subparsers.add_parser('ontology_cli', help='Ontology CLI for class hierarchy, property inheritance, relation inference')

    # visualize_graph
    subparsers.add_parser('visualize_graph', help='Visualize knowledge graph')

    # visualize_network
    subparsers.add_parser('visualize_network', help='Visualize knowledge network')

    # visualize_simple
    subparsers.add_parser('visualize_simple', help='Simple visualization')

    # Global options
    parser.add_argument('--version', action='version', version='%(prog)s 2.0.0')

    # Parse arguments
    args, remaining_args = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        return 0

    return run_script(args.command, remaining_args)


if __name__ == '__main__':
    sys.exit(main())