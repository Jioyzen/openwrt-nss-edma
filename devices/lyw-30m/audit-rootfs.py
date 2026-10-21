#!/usr/bin/env python3
"""Map an actual APK rootfs to its configuration, dependencies and runtime modules.

Leaf packages and unloaded modules are review candidates, not removal decisions.
Use a module list from the same image for a meaningful runtime comparison.
"""
import argparse
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('config', type=Path)
    parser.add_argument('--modules', type=Path, help='Saved /proc/modules from this image')
    args = parser.parse_args()
    blocks = (args.root / 'lib/apk/db/installed').read_text().strip().split('\n\n')
    packages, owners = {}, {}
    for block in blocks:
        fields = {}
        directory = ''
        for line in block.splitlines():
            if len(line) < 2 or line[1] != ':':
                continue
            key, value = line[0], line[2:]
            if key == 'F':
                directory = value
            elif key == 'R':
                owners[f'{directory}/{value}'] = fields['P']
            elif key not in fields:
                fields[key] = value
        packages[fields['P']] = fields
    providers = {name: name for name in packages}
    for name, fields in packages.items():
        for alias in fields.get('p', '').split():
            providers[re.split(r'[=<>~]', alias)[0]] = name
    reverse = {name: set() for name in packages}
    missing = []
    for name, fields in packages.items():
        for dep in fields.get('D', '').split():
            if dep.startswith('!'):
                continue
            # APK metadata uses versioned requirements and virtual provides.
            target = providers.get(re.split(r'[=<>~]', dep)[0])
            if target is None:
                missing.append({'package': name, 'dependency': dep})
            else:
                reverse[target].add(name)
    manifest = {line.split(' - ', 1)[0] for line in args.manifest.read_text().splitlines() if line}
    selected = set(re.findall(r'^CONFIG_PACKAGE_(.+)=y$', args.config.read_text(), re.M))
    # PACKAGE_* includes build toggles as well as package names. Only report
    # unmatched entries; don't call all of them missing installed software.
    unmatched = sorted(name for name in selected if name not in providers)
    loaded = set()
    if args.modules:
        loaded = {line.split()[0].replace('-', '_') for line in args.modules.read_text().splitlines() if line}
    modules = []
    for path in sorted((args.root / 'lib/modules').glob('*/*.ko')):
        key = str(path.relative_to(args.root))
        modules.append({'file': key, 'package': owners.get(key), 'bytes': path.stat().st_size,
                        'loaded': path.stem.replace('-', '_') in loaded if args.modules else None})
    unowned = []
    for path in args.root.rglob('*'):
        if path.is_symlink() or not path.is_file():
            continue
        name = str(path.relative_to(args.root))
        if name not in owners and not name.startswith('lib/apk/') and path.stat().st_size >= 4096:
            unowned.append({'file': name, 'bytes': path.stat().st_size})
    services = []
    for path in sorted((args.root / 'etc/rc.d').glob('S*')):
        if path.is_symlink():
            target = path.readlink()
            rel = f'etc/init.d/{target.name}'
            services.append({'entry': path.name, 'script': rel,
                             'package': owners.get(rel), 'exists': (args.root / rel).is_file()})
    errors = [f'Unsatisfied dependency: {x}' for x in missing]
    if manifest != packages.keys():
        errors.append('APK installed database and manifest differ')
    errors += [f'Missing enabled init script: {x["script"]}' for x in services if not x['exists']]
    forbidden = sorted(n for n in packages if n.startswith(('kmod-usb-', 'kmod-usb2', 'kmod-usb3')))
    errors += [f'Unexpected USB package: {n}' for n in forbidden]
    report = {
        'package_count': len(packages), 'selected_PACKAGE_y_count': len(selected),
        'selected_without_installed_provider_or_build_option': unmatched,
        'installed_bytes_metadata': sum(int(x.get('I', 0)) for x in packages.values()),
        'packages': {n: {'installed_bytes': int(f.get('I', 0)), 'depends': f.get('D', '').split(),
                         'required_by': sorted(reverse[n])} for n, f in sorted(packages.items())},
        'leaf_packages_for_review_not_automatic_removal': sorted(n for n in packages if not reverse[n]),
        'modules': modules, 'enabled_startup_scripts': services,
        'unowned_files_at_least_4KiB': sorted(unowned, key=lambda x: -x['bytes']),
        'errors': errors, 'passed': not errors,
        'limitations': 'Metadata closure and image contents only; not routing, throughput or loaded-module liveness proof.',
    }
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
