#!/usr/bin/env python3
import sys
import json
import random
import os
from dotenv import load_dotenv

print("""

  _    _ _     _     _             _____          _
 | |  | (_)   | |   | |           / ____|        | |
 | |__| |_  __| | __| | ___ _ __ | |     ___   __| | ___
 |  __  | |/ _` |/ _` |/ _ \ '_ \| |    / _ \ / _` |/ _ \\
 | |  | | | (_| | (_| |  __/ | | | |___| (_) | (_| |  __/
 |_|  |_|_|\__,_|\__,_|\___|_| |_|\_____\___/ \__,_|\___/

             Kozel Mixer by Aero25x

            Join us to get more scripts
            https://t.me/hidden_coding

""")

# Determine input source.
# If content is piped via stdin (or if a filename is provided as an argument), use it.
input_data = None

if not sys.stdin.isatty():
    # Read from piped standard input.
    try:
        input_data = json.load(sys.stdin)
    except Exception as e:
        print("Error reading JSON from stdin:", e)
        sys.exit(1)
elif len(sys.argv) > 1:
    # Read input file provided as a command line argument.
    input_path = sys.argv[1]
    try:
        with open(input_path, "r") as f:
            input_data = json.load(f)
    except Exception as e:
        print("Error reading JSON from file {}: {}".format(input_path, e))
        sys.exit(1)
else:
    # Fall back to default file "input.json".
    try:
        with open("input.json", "r") as f:
            input_data = json.load(f)
    except Exception as e:
        print("Error reading input.json:", e)
        sys.exit(1)

# Check if input_data is a dict with an asset tag, or a list of wallet schemas.
# We assume that if input_data is a dict, then wallet schemas are stored under a key (e.g., "tasklist").
asset = None
wallet_schemas = None
if isinstance(input_data, dict):
    # Use asset tag if available
    asset = input_data.get("asset")
    wallet_schemas = input_data.get("tasklist")
    if wallet_schemas is None:
        # If no tasklist key, then assume the dict is the wallet schema list.
        wallet_schemas = input_data
else:
    wallet_schemas = input_data

if not wallet_schemas or len(wallet_schemas) == 0:
    print("Input JSON is empty or does not contain any wallet schemas. Please export json from KOZEL.")
    sys.exit(1)

# Define block types that participate in grouping and those that do not break a group.
MIXED_BLOCKS = ["swap", "anyExecute", "reqRpc", "saveVar"]
NOT_BREAK_JOIN_BLOCKS = ["delay"]

def extract_group(block):
    """
    Determine the group identifier for a block.
    For "swap" blocks, the group is "swap".
    For "reqRpc" blocks, the group is derived from the 'symbol' field.
    For "anyExecute" blocks, the group is derived from the 'dex' field.
    """
    if block['block'] == "swap":
        return "swap"
    elif block['block'] == "reqRpc" or  block['block'] == "saveVar":
        try:
            var = block['symbol'].lower()
            group_name = var.split(":")[0]
            return group_name
        except KeyError:
            return None
    elif block['block'] == "anyExecute":
        try:
            var = block['dex'].lower()
            group_name = var.split(":")[0]
            return group_name
        except KeyError:
            return None
    else:
        return None

# Load environment variables.
load_dotenv(dotenv_path=".env")

activate_angry_mode = os.getenv("ANGRY_MODE", "FALSE").lower() == "true"
gas_price_boost = os.getenv("GAS_BOOST_MIN", None)
gas_price_min = int(os.getenv("GAS_BOOST_MIN", "5000000000"))
gas_price_max = int(os.getenv("GAS_BOOST_MAX", "5000000000"))

# Process each wallet schema from the input.
new_schemas = []
for wallet_schema in wallet_schemas:
    segments = []            # List to hold segments: either non-group or group segments.
    current_segment = []     # For accumulating blocks that are not part of a group.
    current_group_segment = None  # For accumulating contiguous group blocks.

    # Iterate over each block in the wallet schema.
    for block in wallet_schema:

        if 'symbol' in block:
            block['symbol'] = block['symbol'].lower()

        if 'dex' in block:
            block['dex'] = block['dex'].lower()

        if 'msg' in block:
            block['msg'] = block['msg'].lower()

        if block['block'] == "anyExecute" and gas_price_boost:
            block['min_amount'] = str(random.randint(gas_price_min, gas_price_max))

        # Check if the block qualifies for grouping.
        if block['block'] in MIXED_BLOCKS and extract_group(block):
            group_id = extract_group(block)
            if current_group_segment is None:
                # If starting a new group, first push any accumulated non-group blocks.
                if current_segment:
                    segments.append({"type": "non-group", "blocks": current_segment})
                    current_segment = []
                # Start a new group segment.
                current_group_segment = {"group": group_id, "blocks": [block]}
            else:
                # Already in a group: check if the new block belongs to the same group.
                if group_id == current_group_segment["group"]:
                    current_group_segment["blocks"].append(block)
                else:
                    # Group changed: finalize the current group segment and start a new one.
                    segments.append({"type": "group", "group": current_group_segment["group"], "blocks": current_group_segment["blocks"]})
                    current_group_segment = {"group": group_id, "blocks": [block]}
        elif block['block'] in NOT_BREAK_JOIN_BLOCKS:
            # For blocks that should join a group if one is active; otherwise, treat as non-group.
            if current_group_segment is not None:
                current_group_segment["blocks"].append(block)
            else:
                current_segment.append(block)
        else:
            # For blocks that are not part of grouping, flush any active group segment first.
            if current_group_segment is not None:
                segments.append({"type": "group", "group": current_group_segment["group"], "blocks": current_group_segment["blocks"]})
                current_group_segment = None

            if block['block'] == "wallet" and activate_angry_mode:
                block["msg"] = "angry_mode"

            current_segment.append(block)

    # After iterating through all blocks, add any remaining active segments.
    if current_group_segment is not None:
        segments.append({"type": "group", "group": current_group_segment["group"], "blocks": current_group_segment["blocks"]})
    if current_segment:
        segments.append({"type": "non-group", "blocks": current_segment})

    # Identify indices of all group segments.
    group_indices = [i for i, seg in enumerate(segments) if seg["type"] == "group"]
    group_segments = [segments[i] for i in group_indices]

    # Shuffle the group segments (the order within each group remains unchanged).
    random.shuffle(group_segments)

    # Reinsert the shuffled group segments back into their original positions.
    for i, idx in enumerate(group_indices):
        segments[idx] = group_segments[i]

    # Flatten the segments to form the new wallet schema.
    new_schema = []
    for seg in segments:
        new_schema.extend(seg["blocks"])
    new_schemas.append(new_schema)

# Prepare output JSON. If there's an asset tag from the input, include it.
output_data = {"uid": asset if asset else "mixed_data", "tasklist": new_schemas}

# Write the new schemas to an output file.
with open("output.json", "w") as f:
    json.dump(output_data, f, indent=2)

print("Output written to output.json")

