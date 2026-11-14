"""Ebbinghaus-style forgetting over a memory string.

Used by the "ebbinghaus" method in forgetting.py, which builds the input string
and reads the output back. The algorithm itself only knows about strings.
"""
import math
import re


def llm_forgetting_algorithm(memory_str: str, current_time: int, retention_threshold: float = 0.3, drop_threshold: float = 0.1) -> str:
    """
    Memory forgetting algorithm for an LLM; both input and output are strings.

    Expected input format (one memory per line):
    [Time: 1] [Importance: 0.8] [Access: 3] User likes writing low-level C code.
    [Time: 10] [Importance: 0.5] [Access: 1] Ate a sandwich for lunch.
    """
    lines = memory_str.strip().split('\n')
    updated_memories = []

    # Regular expression that parses the metadata
    pattern = re.compile(r"\[Time:\s*(\d+)\]\s*\[Importance:\s*([\d.]+)\]\s*\[Access:\s*(\d+)\]\s*(.*)")

    for line in lines:
        if not line.strip():
            continue

        match = pattern.match(line)
        if not match:
            # Wrong format: keep it as plain text
            updated_memories.append(line)
            continue

        mem_time = int(match.group(1))
        importance = float(match.group(2))
        access_count = int(match.group(3))
        content = match.group(4)

        # Elapsed time delta_t
        delta_t = max(0, current_time - mem_time)

        # Memory strength S: from the initial importance and the access count
        # (the more often it is accessed, the better it resists forgetting)
        strength = importance * (1 + math.log(1 + access_count))

        # Ebbinghaus forgetting curve
        if strength == 0:
            retention = 0.0
        else:
            # The time coefficient shapes the decay curve
            retention = math.exp(-delta_t / (strength * 10.0))

        # Handle the memory according to its retention score
        if retention < drop_threshold:
            # Completely forgotten: drop the memory
            continue
        elif retention < retention_threshold:
            # Fading: keep the core but blur part of the details
            faded_content = fade_memory_content(content)
            updated_line = f"[Time: {mem_time}] [Importance: {importance}] [Access: {access_count}] [FADED] {faded_content}"
            updated_memories.append(updated_line)
        else:
            # Still clear: keep as is
            updated_memories.append(line)

    return "\n".join(updated_memories)


def fade_memory_content(content: str) -> str:
    """Blur a memory: keep the first words and replace the details with a vague marker."""
    words = content.split()
    if len(words) > 3:
        return " ".join(words[:2]) + " ... [details forgotten]"
    return content + " [vague]"
