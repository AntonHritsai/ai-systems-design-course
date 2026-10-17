"""Save an interactively entered key outside the course clone; never print it."""
import getpass
import os
from pathlib import Path
import re

destination = Path('/Users/antonygritsai/Desktop/Sobol/.lab03-openrouter-key')
key = getpass.getpass('OpenRouter API key (hidden input): ').strip()
if not re.fullmatch(r'sk-or-v1-[A-Za-z0-9]{30,}', key):
    raise SystemExit('Key format is invalid. No file was created.')
descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'w') as stream:
    stream.write(key)
del key
print('Key saved outside the repository. Its value was not printed.')
print(destination)
