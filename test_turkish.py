#!/usr/bin/env python3
"""Test Turkish content generation in WriterAgent."""
import sys, time, os
os.chdir('/usr/local/lib/hermes-agent/plugins/haber-kurator')
sys.path.insert(0, '.')

from writer_agent import WriterAgent
from haber_kurator_core import HaberKuratorCore
from pathlib import Path

core = HaberKuratorCore(Path('.'))
agent = WriterAgent(core)
agent.set_llm(True)

print(f'_llm_available: {agent._llm_available}')
print()

titles = [
    'Trump warns clock is ticking for Iran as peace progress stalls',
    'Elon Musk said control of OpenAI should go to his children',
    'Business Daily',
]

for title in titles:
    t0 = time.time()
    result = agent._translate_headline(title)
    elapsed = time.time() - t0
    status = '✅' if result != title else '❌ English!'
    print(f'{status} ({elapsed:.1f}s)')
    print(f'  Original: {title}')
    print(f'  Turkish:  {result}')
    print()
