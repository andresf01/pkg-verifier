#!/usr/bin/env python3
import os
import subprocess
import json
import argparse
from typing import List, Dict, Any, Set

bad_packages = ['angulartics2@14.1.2','@ctrl/deluge@7.2.2','@ctrl/golang-template@1.4.3','@ctrl/magnet-link@4.0.4','@ctrl/ngx-codemirror@7.0.2','@ctrl/ngx-csv@6.0.2','@ctrl/ngx-emoji-mart@9.2.2','@ctrl/ngx-rightclick@4.0.2','@ctrl/qbittorrent@9.7.2','@ctrl/react-adsense@2.0.2','@ctrl/shared-torrent@6.3.2','@ctrl/tinycolor@4.1.1, @4.1.2','@ctrl/torrent-file@4.1.2','@ctrl/transmission@7.3.1','@ctrl/ts-base32@4.0.2','encounter-playground@0.0.5','json-rules-engine-simplified@0.2.4, 0.2.1','koa2-swagger-ui@5.11.2, 5.11.1','@nativescript-community/gesturehandler@2.0.35','@nativescript-community/sentry 4.6.43','@nativescript-community/text@1.6.13','@nativescript-community/ui-collectionview@6.0.6','@nativescript-community/ui-drawer@0.1.30','@nativescript-community/ui-image@4.5.6','@nativescript-community/ui-material-bottomsheet@7.2.72','@nativescript-community/ui-material-core@7.2.76','@nativescript-community/ui-material-core-tabs@7.2.76','ngx-color@10.0.2','ngx-toastr@19.0.2','ngx-trend@8.0.1','react-complaint-image@0.0.35','react-jsonschema-form-conditionals@0.3.21','react-jsonschema-form-extras@1.0.4','rxnt-authentication@0.0.6','rxnt-healthchecks-nestjs@1.0.5','rxnt-kue@1.0.7','swc-plugin-component-annotate@1.9.2','ts-gaussian@3.0.6','@crowdstrike/commitlint@8.1.1, 8.1.2','@crowdstrike/falcon-shoelace@0.4.2','@crowdstrike/foundry-js@0.19.2','@crowdstrike/glide-core@0.34.2, 0.34.3','@crowdstrike/logscale-dashboard@1.205.2','@crowdstrike/logscale-file-editor@1.205.2','@crowdstrike/logscale-parser-edit@1.205.1, 1.205.2','@crowdstrike/logscale-search@1.205.2','@crowdstrike/tailwind-toucan-base@5.0.2','browser-webdriver-downloader@3.0.8','ember-browser-services@5.0.3','ember-headless-form-yup@1.0.1','ember-headless-form@1.1.3','ember-headless-table@2.1.6','ember-url-hash-polyfill@1.0.13','ember-velcro@2.2.2','eslint-config-crowdstrike-node@4.0.4','eslint-config-crowdstrike@11.0.3','monorepo-next@13.0.2','remark-preset-lint-crowdstrike@4.0.2','verror-extra@6.0.1','yargs-help-output@5.0.3', 'debug@4.4.2']

def list_node_packages(project_path: str, depth: int = 10, manager = None) -> List[str]:
    """
    Lists installed Node.js packages for a given project path up to a specific depth.

    Args:
        project_path: The absolute or relative path to the project directory.
        depth: The maximum dependency depth to traverse. Defaults to 10.

    Returns:
        A sorted list of unique 'package@version' entries.

    Raises:
        FileNotFoundError: If the provided path does not exist or is not a directory.
        subprocess.CalledProcessError: If the package manager command fails.
    """
    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"Directory not found at '{project_path}'")

    # --- 1. Determine package manager and command ---
    manager_arg = None
    command = []
    depth_arg = f'--depth={depth}'

    if manager == 'pnpm' or os.path.exists(os.path.join(project_path, 'pnpm-lock.yaml')):
        manager_arg = 'pnpm'
        command = ['pnpm', 'list', '--json', depth_arg]
    elif manager == 'yarn' or os.path.exists(os.path.join(project_path, 'yarn.lock')):
        manager_arg = 'yarn'
        command = ['yarn', 'list', '--json', depth_arg]
    elif manager == 'npm' or os.path.exists(os.path.join(project_path, 'package-lock.json')) or \
         os.path.exists(os.path.join(project_path, 'node_modules')):
        manager_arg = 'npm'
        # npm uses --depth= instead of --depth 
        command = ['npm', 'list', '--json', f'--depth={depth}']
    else:
        print(f"Warning: No lock file found in '{project_path}'.")
        return []

    # --- 2. Execute the list command ---
    try:
        result = subprocess.run(
            command,
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        stdout = result.stdout
    except FileNotFoundError:
        print(f"Error: '{command[0]}' not found. Is it installed and in your PATH?")
        return []
    except subprocess.CalledProcessError as e:
        if manager_arg == 'npm' and e.returncode == 1 and not e.stderr:
             return []
        print(f"Error running '{' '.join(command)}' in '{project_path}':")
        print(e.stderr)
        raise e

    # --- 3. Recursively parse the JSON output ---
    packages_set: Set[str] = set()
    
    def _parse_npm_pnpm_recursive(deps: Dict[str, Any]):
        """Helper to recursively parse npm and pnpm dependency trees."""
        for name, details in deps.items():
            version = details.get('version')
            if version:
                packages_set.add(f"{name}@{version}")
            if 'dependencies' in details:
                _parse_npm_pnpm_recursive(details['dependencies'])

    def _parse_yarn_recursive(trees: List[Dict[str, Any]]):
        """Helper to recursively parse yarn dependency trees."""
        for item in trees:
            if 'name' in item:
                packages_set.add(item['name'])
            if 'trees' in item and item['trees']:
                _parse_yarn_recursive(item['trees'])

    try:
        if manager_arg in ['npm', 'pnpm']:
            data = json.loads(stdout)
            root = data[0] if manager_arg == 'pnpm' and data else data
            if 'dependencies' in root:
                _parse_npm_pnpm_recursive(root['dependencies'])
        
        elif manager_arg == 'yarn':
            for line in stdout.strip().split('\n'):
                data = json.loads(line)
                if data.get('type') == 'tree':
                    if 'trees' in data.get('data', {}):
                        _parse_yarn_recursive(data['data']['trees'])
                    break
    
    except (json.JSONDecodeError, IndexError) as e:
        print(f"Error: Could not parse JSON output from {manager_arg}. Details: {e}")
        return []

    return sorted(list(packages_set))

# --- Main execution block ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="List npm, yarn, or pnpm packages in a project directory up to a given depth.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'path',
        nargs='?',
        default=os.getcwd(),
        help="The path to the project directory.\n(defaults to the current working directory)"
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=10,
        help="The maximum depth of dependencies to list.\n(defaults to 10)"
    )
    parser.add_argument(
        '--manager',
        default=None,
        help="The package manager (npm, pnpm, yarn)"
    )
    args = parser.parse_args()
    target_path = os.path.abspath(args.path)

    try:
        print(f"🔍 Checking for packages in: '{target_path}' (up to depth {args.depth})")
        
        installed_packages = list_node_packages(target_path, depth=args.depth, manager=args.manager)

        infected_packages = []
        
        if installed_packages:
            print(f"\n✅ Found {len(installed_packages)} unique packages:")
            for pkg in installed_packages:
                if pkg in bad_packages:
                    infected_packages.append(pkg)
                print(f"   - {pkg}")
        else:
            print("\nℹ️ No packages found.")

        if (len(infected_packages)):
            print(f"\n⚠️  Some packages are infected ⚠️")
            for pkg in infected_packages:
                print(f"   - {pkg}")
        else:
            print(f"\n✅ You are clear")
            
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
    except subprocess.CalledProcessError:
        print(f"\n❌ A package manager command failed. Please check the errors above.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")