import re

with open('frontend/src/app/app.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
last_depth = 0
first_neg = None
for i, l in enumerate(lines, 1):
    o = len(re.findall(r'<section[> ]', l))
    c = len(re.findall(r'</section>', l))
    for _ in range(o):
        depth += 1
    for _ in range(c):
        depth -= 1
    if depth < 0 and first_neg is None:
        first_neg = i
        depth = 0
    if depth != last_depth:
        print(f'{last_depth:2d} -> {depth:2d}  line {i}  {l.strip()[:80]}')
        last_depth = depth

print(f'Final depth: {depth}')
print(f'First negative depth at line: {first_neg}')
