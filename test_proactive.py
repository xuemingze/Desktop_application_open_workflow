"""Smoke test for proactive_sniff module"""
from collections import deque
from proactive_sniff import (
    UserProfile, QuestionGenerator, ProactiveScheduler,
    ProactiveRunner, ProactiveQuestion,
)
from context_agent import EchoBackend

# 1. Profile
profile = UserProfile(
    hobbies="爬山、摄影",
    interests="AI、独立游戏",
    learning="Rust 编程",
    work="桌面自动化",
)
print("Profile empty?", profile.is_empty())
print("Profile prompt:")
print(profile.to_prompt())
print()

# 2. Generator
backend = EchoBackend()
generator = QuestionGenerator(backend)
print("--- Question Generator ---")
q = generator.generate(profile, [])
print(f"Question: {q}")
print()

# 3. Dedup logic (using scheduler internals)
hist = deque()
hist.append(ProactiveQuestion(text="test question 1", category="chat", timestamp=0))
hist.append(ProactiveQuestion(text="test question 2", category="work", timestamp=1))

# Mock scheduler just for dedup test
from PySide6.QtCore import QCoreApplication
import sys
app = QCoreApplication.instance() or QCoreApplication(sys.argv)

scheduler = ProactiveScheduler(generator, hist)
scheduler.set_profile(profile)
scheduler.set_daily_count(3)

print("--- Dedup test ---")
test_dup = ProactiveQuestion(text="test question 1", category="chat", timestamp=99)
print(f"Is duplicate of existing? {scheduler._is_duplicate(test_dup)}")

test_new = ProactiveQuestion(text="something different", category="hobby", timestamp=99)
print(f"Is duplicate of new text? {scheduler._is_duplicate(test_new)}")

print()
print("--- Status (not started) ---")
print(scheduler.get_status())
print()

print("All smoke tests passed!")
