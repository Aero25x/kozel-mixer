#!/usr/bin/env python3
import sys
import json
import random
import os
from dotenv import load_dotenv
import argparse

# -----------------------------------------------------------------------------
# Kozel Mixer by Aero25x
#   Enhanced with command-line argument parsing for input/output files
#   Usage: python kozel_mixer.py [-i INPUT_JSON] [-o OUTPUT_JSON]
# -----------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Kozel Mixer script with CLI args for input/output files")
    parser.add_argument(
        '-i', '--input',
        help="Path to input JSON file. If omitted and there's data on stdin, uses stdin. Otherwise defaults to 'input.json'.",
        default=None
    )
    parser.add_argument(
        '-o', '--output',
        help="Path to output JSON file. Defaults to 'output.json'.",
        default='output.json'
    )
    return parser.parse_args()


def extract_group(block):
    btype = block.get('block')
    if btype == "swap":
        return "swap"
    elif btype in ("reqRpc", "saveVar"):
        var = block.get('symbol','').lower()
        return var.split(':')[0] if var else None
    elif btype == "anyExecute":
        dex = block.get('dex','').lower()
        return dex.split(':')[0] if dex else None
    return None


def main():
    args = parse_args()

    print(r"""
  _    _ _     _     _             _____          _
 | |  | (_)   | |   | |           / ____|        | |
 | |__| |_  __| | __| | ___ _ __ | |     ___   __| | ___
 |  __  | |/ _` |/ _` |/ _ \ '_ \| |    / _ \ / _` |/ _ \
 | |  | | | (_| | (_| |  __/ | | | |___| (_) | (_| |  __/
 |_|  |_|_|\__,_|\__,_|\___|_| |_|\_____\___/\__,_|\___|

             Kozel Mixer by Aero25x

            Join us to get more scripts
            https://t.me/hidden_coding

""")

    # Load environment variables
    dotenv_path = os.getenv('DOTENV_PATH', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    # Configurable flags and parameters
    activate_angry_mode = os.getenv("ANGRY_MODE", "FALSE").lower() == "true"
    use_proxy = os.getenv("USE_PROXY", "FALSE").lower() == "true"
    gas_price_min = int(os.getenv("GAS_BOOST_MIN", "5000000000"))
    gas_price_max = int(os.getenv("GAS_BOOST_MAX", "6000000000"))

    # Load proxy list if needed
    proxy_list = []
    if use_proxy:
        try:
            with open("proxy.txt", "r") as f:
                proxy_list = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print("Proxy file not found, continuing without proxies.")

    # Determine input source
    input_data = None
    try:
        if not sys.stdin.isatty():
            input_data = json.load(sys.stdin)
        elif args.input:
            with open(args.input, 'r') as f:
                input_data = json.load(f)
        else:
            with open('input.json', 'r') as f:
                input_data = json.load(f)
    except Exception as e:
        print(f"Error reading input JSON: {e}")
        sys.exit(1)

    # Process data as before
    asset = None
    wallet_schemas = []
    if isinstance(input_data, dict):
        asset = input_data.get('asset')
        wallet_schemas = input_data.get('tasklist') or []
    elif isinstance(input_data, list):
        wallet_schemas = input_data

    if not wallet_schemas:
        print("Input JSON is empty or does not contain any wallet schemas. Please export JSON from KOZEL.")
        sys.exit(1)

    MIXED_BLOCKS = ["swap", "anyExecute", "reqRpc", "saveVar"]
    NOT_BREAK_JOIN_BLOCKS = ["delay"]

    new_schemas = []
    for wallet_schema in wallet_schemas:
        segments = []
        current_segment = []
        current_group_segment = None

        for block in wallet_schema:
            # Normalize keys
            for key in ('symbol', 'dex', 'msg'):
                if key in block and isinstance(block[key], str):
                    block[key] = block[key].lower()
            # Ensure amount is int
            if 'amount' in block:
                try:
                    block['amount'] = int(block['amount'])
                except (ValueError, TypeError):
                    pass
            # Random gas boost
            if block.get('block') == 'anyExecute':
                block['min_amount'] = str(random.randint(gas_price_min, gas_price_max))

            # Grouping logic
            group_id = extract_group(block) if block.get('block') in MIXED_BLOCKS else None
            if group_id:
                if current_group_segment is None:
                    if current_segment:
                        segments.append({'type':'non-group','blocks':current_segment})
                        current_segment = []
                    current_group_segment = {'group':group_id,'blocks':[block]}
                elif group_id == current_group_segment['group']:
                    current_group_segment['blocks'].append(block)
                else:
                    segments.append({'type':'group','group':current_group_segment['group'],'blocks':current_group_segment['blocks']})
                    current_group_segment = {'group':group_id,'blocks':[block]}
            elif block.get('block') in NOT_BREAK_JOIN_BLOCKS and current_group_segment:
                current_group_segment['blocks'].append(block)
            else:
                if current_group_segment:
                    segments.append({'type':'group','group':current_group_segment['group'],'blocks':current_group_segment['blocks']})
                    current_group_segment = None
                # Apply wallet modifications
                if block.get('block') == 'wallet':
                    if activate_angry_mode:
                        block['msg'] = 'angry_mode'
                    if use_proxy and proxy_list:
                        proxy = random.choice(proxy_list)
                        block['proxy'] = proxy if proxy.startswith('http') else f"http://{proxy}"
                current_segment.append(block)

        # Flush leftovers
        if current_group_segment:
            segments.append({'type':'group','group':current_group_segment['group'],'blocks':current_group_segment['blocks']})
        if current_segment:
            segments.append({'type':'non-group','blocks':current_segment})

        # Shuffle group segments
        group_segments = [seg for seg in segments if seg['type']=='group']
        random.shuffle(group_segments)
        group_positions = [i for i, seg in enumerate(segments) if seg['type']=='group']
        for idx, pos in enumerate(group_positions):
            segments[pos] = group_segments[idx]

        # Flatten back
        new_schema = []
        for seg in segments:
            new_schema.extend(seg['blocks'])
        new_schemas.append(new_schema)

    # Write output to specified file
    output_path = args.output
    output_data = {'uid': asset if asset else 'mixed_data', 'tasklist': new_schemas}
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Output written to {output_path}")


if __name__ == '__main__':
    main()
