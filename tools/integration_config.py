"""Lossless, bounded MCP-entry edits; unsupported syntax is never normalized."""
import json
import tomllib

import integration_contract as c

CLIENTS = ("codex-config", "claude-code-project", "claude-desktop")
FILENAMES = dict(zip(CLIENTS, ("config.toml", ".mcp.json", "claude_desktop_config.json")))


def parsed(client, data):
    c.require(len(data) <= c.LIMIT, "CONFIG_SIZE")
    text = data.decode("utf-8", errors="strict")
    value = tomllib.loads(text) if client == "codex-config" else c.decode(data)
    c.require(isinstance(value, dict), "CONFIG_OBJECT")
    key = "mcp_servers" if client == "codex-config" else "mcpServers"
    c.require(key not in value or isinstance(value[key], dict), "CONFIG_SERVERS_OBJECT")
    return text, value, key


def members(text, start=0):
    """Use the standard JSON decoder for value boundaries, not brace matching."""
    decoder = json.JSONDecoder()
    pos = start
    while text[pos].isspace():
        pos += 1
    c.require(text[pos] == "{", "CONFIG_OBJECT")
    pos += 1
    rows, previous = {}, None
    while True:
        while text[pos].isspace():
            pos += 1
        if text[pos] == "}":
            return rows, pos
        begin = pos
        key, pos = decoder.raw_decode(text, pos)
        while text[pos].isspace():
            pos += 1
        c.require(text[pos] == ":", "CONFIG_OBJECT")
        pos += 1
        while text[pos].isspace():
            pos += 1
        value_start = pos
        _, end = decoder.raw_decode(text, pos)
        pos = end
        while text[pos].isspace():
            pos += 1
        rows[key] = (begin, value_start, end, previous, pos)
        if text[pos] == "}":
            return rows, pos
        c.require(text[pos] == ",", "CONFIG_OBJECT")
        previous, pos = pos, pos + 1


def drop(text, row):
    begin, _, end, previous, following = row
    if previous is not None:
        return text[:previous] + text[end:]
    if text[following] == ",":
        return text[:begin] + text[following + 1:]
    return text[:begin] + text[end:]


def block(name, entry):
    # Names are identifier-shaped and strings use TOML-compatible JSON quoting.
    c._validate(name, c.ID)
    return ("\n# BEGIN GOLEM MCP " + name + "\n[mcp_servers." + json.dumps(name) + "]\n" +
            "command = " + json.dumps(entry["command"], ensure_ascii=True) + "\n" +
            "args = " + json.dumps(entry["args"], ensure_ascii=True) + "\n" +
            "# END GOLEM MCP " + name + "\n")


def managed(client, data, name, entry):
    text, value, key = parsed(client, data)
    c.require(value.get(key, {}).get(name) == entry, "MANAGED_CONFIG_DRIFT")
    if client == "codex-config":
        expected = block(name, entry)
        c.require(text.count(expected) == 1, "MANAGED_CONFIG_DRIFT")
    else:
        row = members(text, members(text)[0][key][1])[0][name]
        c.require(text[row[1]:row[2]] == json.dumps(entry, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
                  "MANAGED_CONFIG_DRIFT")


def edit(client, data, name, entry, *, remove=False, created_container=False):
    c.require(client in CLIENTS, "CLIENT_CONFIG_UNSUPPORTED")
    c._validate(name, c.ID)
    text, value, key = parsed(client, data)
    before = value.get(key, {})
    if remove:
        managed(client, data, name, entry)
        if client == "codex-config":
            result = text.replace(block(name, entry), "", 1)
        else:
            root_rows = members(text)[0]
            rows = members(text, root_rows[key][1])[0]
            result = drop(text, root_rows[key] if created_container and len(rows) == 1 else rows[name])
        expected = {k: v for k, v in before.items() if k != name}
    else:
        c.require(name not in before, "SERVER_NAME_CONFLICT")
        if client == "codex-config":
            result = text + block(name, entry)
        else:
            rows, closing = members(text)
            encoded = json.dumps(entry, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            if key in rows:
                servers, closing = members(text, rows[key][1])
                addition = ("," if servers else "") + json.dumps(name) + ":" + encoded
            else:
                addition = ("," if rows else "") + '"mcpServers":{' + json.dumps(name) + ":" + encoded + "}"
            result = text[:closing] + addition + text[closing:]
        expected = {**before, name: entry}
    output = result.encode("utf-8")
    _, actual, _ = parsed(client, output)
    c.require(actual.get(key, {}) == expected and
              {k: v for k, v in value.items() if k != key} ==
              {k: v for k, v in actual.items() if k != key}, "CONFIG_SEMANTICS_CHANGED")
    return output, key not in value
