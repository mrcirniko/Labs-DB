import pandas as pd
import random
import ftfy
from tqdm import tqdm

df = pd.read_csv('cv/Curriculum Vitae.csv', encoding='utf-8')
df['Resume'] = df['Resume'].apply(str)

df['Resume'] = df['Resume'].apply(ftfy.fix_text)

category_blocks = {}

for _, row in tqdm(df.iterrows(), total=len(df)):
    category = row['Category']
    resume = row['Resume']

    parts = resume.split('\r\n')

    valid_blocks = [ftfy.fix_text(p.strip()) for p in parts if len(p.strip()) > 100 and 'skill' in p.lower()]

    if category not in category_blocks:
        category_blocks[category] = set()

    category_blocks[category].update(valid_blocks)

category_blocks = {cat: list(blocks) for cat, blocks in category_blocks.items() if blocks}

N = 500000
new_data = {
    'Category': [],
    'Resume': [],
}

categories = list(category_blocks.keys())

for _ in tqdm(range(N)):
    cat = random.choice(categories)
    block = random.choice(category_blocks[cat])
    new_data['Category'].append(cat)
    new_data['Resume'].append(block)

synthetic_df = pd.DataFrame(new_data)

synthetic_df.to_csv('synthetic_resumes.csv', index=False, encoding='utf-8')

