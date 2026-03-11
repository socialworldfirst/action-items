import os
import re
import json
from datetime import datetime, timezone


def extract_data(html):
    match = re.search(r'const DATA = (\{.*?\});', html, re.DOTALL)
    if not match:
        raise ValueError("Could not find DATA block")
    js_obj = match.group(1)
    # Convert JS object to valid JSON
    js_obj = re.sub(r'(\w+):', r'"\1":', js_obj)  # quote keys
    js_obj = js_obj.replace("'", '"')  # single to double quotes
    # Handle trailing commas
    js_obj = re.sub(r',\s*([}\]])', r'\1', js_obj)
    return json.loads(js_obj), match


def rebuild_js(data):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    data['updated'] = now

    lines = ['const DATA = {']
    lines.append(f'  updated: "{data["updated"]}",')
    lines.append('  tiers: {')

    tier_keys = ['t1', 't2', 't3', 't4']
    tier_colors = {'t1': '#DC2626', 't2': '#F59E0B', 't3': '#3B82F6', 't4': '#6B7280'}

    for ti, tk in enumerate(tier_keys):
        tier = data['tiers'][tk]
        lines.append(f'    {tk}: {{')
        lines.append(f'      color: "{tier_colors[tk]}",')
        lines.append('      items: [')

        for i, item in enumerate(tier['items']):
            item['id'] = f'{tk}-{i+1}'
            task_esc = item['task'].replace('"', '\\"')
            notes_esc = item['notes'].replace('"', '\\"')
            comma = ',' if i < len(tier['items']) - 1 else ''
            lines.append(f'        {{ id: "{item["id"]}", type: "{item["type"]}", task: "{task_esc}", notes: "{notes_esc}" }}{comma}')

        lines.append('      ]')
        comma = ',' if ti < len(tier_keys) - 1 else ''
        lines.append(f'    }}{comma}')

    lines.append('  }')
    lines.append('};')
    return '\n'.join(lines)


def parse_changes(body):
    changes = []
    for line in body.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        m = re.match(r'(T[1-4])-(\d+)\s+"([^"]+)"(.*)', line, re.IGNORECASE)
        if not m:
            continue

        tier = m.group(1).lower()
        num = int(m.group(2))
        task_name = m.group(3)
        rest = m.group(4).strip()

        action = None
        comment = None

        parts = re.split(r'\s*\u2014\s*', rest)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            upper = part.upper()
            if upper == 'MARK DONE':
                action = 'done'
            elif upper == 'MOVE UP':
                action = 'move-up'
            elif upper == 'MOVE DOWN':
                action = 'move-down'
            elif upper == 'CHANGE TO EXTERNAL':
                action = 'to-external'
            elif upper == 'CHANGE TO MY INPUT':
                action = 'to-myinput'
            elif part.startswith('REMINDER'):
                continue  # skip reminder info
            else:
                comment = part

        changes.append({
            'tier': tier,
            'num': num,
            'task': task_name,
            'action': action,
            'comment': comment,
        })

    return changes


def apply_changes(data, changes):
    tier_order = ['t1', 't2', 't3', 't4']

    for ch in changes:
        tier = ch['tier']
        idx = ch['num'] - 1

        if tier not in data['tiers']:
            continue
        items = data['tiers'][tier]['items']
        if idx < 0 or idx >= len(items):
            continue

        item = items[idx]

        if ch['comment']:
            if item['notes']:
                item['notes'] += ' | ' + ch['comment']
            else:
                item['notes'] = ch['comment']

        if ch['action'] == 'done':
            items.pop(idx)
        elif ch['action'] == 'to-external':
            item['type'] = 'EXTERNAL'
        elif ch['action'] == 'to-myinput':
            item['type'] = 'MY INPUT'
        elif ch['action'] == 'move-up':
            ti = tier_order.index(tier)
            if ti > 0:
                items.pop(idx)
                data['tiers'][tier_order[ti - 1]]['items'].append(item)
        elif ch['action'] == 'move-down':
            ti = tier_order.index(tier)
            if ti < 3:
                items.pop(idx)
                data['tiers'][tier_order[ti + 1]]['items'].append(item)


def main():
    with open('index.html', 'r') as f:
        html = f.read()

    data, match = extract_data(html)
    changes_body = os.environ.get('ISSUE_BODY', '')
    changes = parse_changes(changes_body)

    if not changes:
        print("No valid changes found")
        return

    apply_changes(data, changes)
    new_js = rebuild_js(data)
    new_html = html[:match.start()] + new_js + html[match.end():]

    with open('index.html', 'w') as f:
        f.write(new_html)

    print(f"Applied {len(changes)} change(s)")


if __name__ == '__main__':
    main()
