import os
import re
import anthropic
from datetime import datetime


def main():
    with open('index.html', 'r') as f:
        html = f.read()

    match = re.search(r'const DATA = \{.*?\};', html, re.DOTALL)
    if not match:
        print("ERROR: Could not find DATA block")
        exit(1)

    current_data = match.group(0)
    changes = os.environ.get('ISSUE_BODY', '')
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""You manage an action items list with 4 tiers (T1-T4). Here is the current DATA JavaScript object:

{current_data}

The user submitted these changes from the live dashboard:

{changes}

Apply ALL requested changes and return ONLY the updated JavaScript code — from `const DATA = {{` through the closing `}};`. Nothing else, no markdown fences.

Rules:
- Set `updated` to "{now}"
- MARK DONE = remove the item entirely
- MOVE UP = move item to the tier above (t2->t1, t3->t2, t4->t3)
- MOVE DOWN = move item to the tier below (t1->t2, t2->t3, t3->t4)
- change to EXTERNAL / MY INPUT = change the type field
- Re-number item IDs sequentially after changes (t1-1, t1-2, etc.)
- User comments = update the notes field with the new context
- TASK = short action-verb goal, no people names
- NOTES = detail, people, context, deadlines
- NEVER drop items unless explicitly marked done
- Keep all tier colors unchanged: t1=#DC2626, t2=#F59E0B, t3=#3B82F6, t4=#6B7280"""
        }]
    )

    result = response.content[0].text

    # Strip markdown fences if present
    result = re.sub(r'^```(?:javascript|js)?\s*\n', '', result)
    result = re.sub(r'\n```\s*$', '', result)

    code_match = re.search(r'(const DATA = \{.*?\};)', result, re.DOTALL)
    if code_match:
        new_data = code_match.group(1)
    else:
        new_data = result.strip()

    new_html = html[:match.start()] + new_data + html[match.end():]

    with open('index.html', 'w') as f:
        f.write(new_html)

    print("Successfully updated DATA block")


if __name__ == '__main__':
    main()
