#!/usr/bin/env python3

print("""



  _    _ _     _     _             _____          _
 | |  | (_)   | |   | |           / ____|        | |
 | |__| |_  __| | __| | ___ _ __ | |     ___   __| | ___
 |  __  | |/ _` |/ _` |/ _ \ '_ \| |    / _ \ / _` |/ _ \\
 | |  | | | (_| | (_| |  __/ | | | |___| (_) | (_| |  __/
 |_|  |_|_|\__,_|\__,_|\___|_| |_|\_____\___/ \__,_|\___|

             Kozel Mixer by Aero25x

            Join us to get more scripts
            https://t.me/hidden_coding


    """)



import json
import random
from dotenv import load_dotenv
import os



# Define block types that participate in grouping and those that do not break a group.
MIXED_BLOCKS = ["swap", "anyExecute", "reqRpc", "saveVar"]
NOT_BREAK_JOIN_BLOCKS = ["delay"]

# Load input JSON.
with open("input.json", "r") as f:
    input_json = json.load(f)

if len(input_json) == 0:
    print("Input json is empty: please export json from KOZEL")
    exit(1)

def extract_group(block):
    """
    Determine the group identifier for a block.
    For "swap" blocks, the group is "swap".
    For "reqRpc" blocks, the group is derived from the 'symbol' field.
    For "anyExecute" blocks, the group is derived from the 'dex' field.
    """
    if block['block'] == "swap":
        return "swap"
    elif block['block'] == "reqRpc":
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



load_dotenv(dotenv_path=".env")

activate_angry_mode = os.getenv("ANGRY_MODE", "FALSE").lower() == "true"
gas_price_boost = os.getenv("GAS_BOOST_MIN", None)
gas_price_min = int(os.getenv("GAS_BOOST_MIN", "5000000000"))
gas_price_max = int(os.getenv("GAS_BOOST_MAX", "5000000000"))



# Process each wallet schema from the input.
new_schemas = []
for wallet_schema in input_json:
    segments = []            # List to hold segments: either non-group or group segments.
    current_segment = []     # For accumulating blocks that do not belong to a group.
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
                # If already in a group, check if the new block belongs to the same group.
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

            if block['block'] == "wallet" and activate_angry_mode == True :
                block["msg"]="angry_mode"

            current_segment.append(block)

    # After iterating through all blocks, add any remaining active segments.
    if current_group_segment is not None:
        segments.append({"type": "group", "group": current_group_segment["group"], "blocks": current_group_segment["blocks"]})
    if current_segment:
        segments.append({"type": "non-group", "blocks": current_segment})

    # Identify positions of all group segments.
    group_indices = [i for i, seg in enumerate(segments) if seg["type"] == "group"]
    group_segments = [segments[i] for i in group_indices]

    # Shuffle the group segments (the order within each group remains unchanged).
    random.shuffle(group_segments)

    # Reinsert the shuffled group segments back into their original placeholder positions.
    for i, idx in enumerate(group_indices):
        segments[idx] = group_segments[i]

    # Flatten the segments to form the new wallet schema.
    new_schema = []
    for seg in segments:
        new_schema.extend(seg["blocks"])
    new_schemas.append(new_schema)

# Write the new schemas to an output file.
with open("output.json", "w") as f:
    json.dump({"uid":"mixed_data", "tasklist":new_schemas}, f, indent=2)
