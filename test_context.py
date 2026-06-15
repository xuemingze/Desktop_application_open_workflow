"""Quick smoke test for context_aware components"""
from context_agent import parse_intent_response, EchoBackend

# Test JSON parsing
r1 = parse_intent_response('{"need_action": true, "intent": "test", "message": "hi"}')
print(f"Test 1 (clean JSON): {r1}")

r2 = parse_intent_response('```json\n{"need_action": true, "intent": "test"}\n```')
print(f"Test 2 (markdown): {r2}")

r3 = parse_intent_response('not json at all')
print(f"Test 3 (invalid): {r3}")

# Test EchoBackend
backend = EchoBackend()
print("\n--- EchoBackend tests ---")
print(f"IP: {backend.infer('test', '192.168.1.1')}")
print(f"Error: {backend.infer('test', 'Traceback (most recent call last):')}")
print(f"Random: {backend.infer('test', 'hello world')}")

# Test Gatekeeper
from context_sensor import ContextCapsule
from context_gatekeeper import Gatekeeper

gk = Gatekeeper()
print("\n--- Gatekeeper tests ---")

cap1 = ContextCapsule(source='clipboard', clipboard_text='192.168.1.100', foreground_app='code.exe')
print(f"IP: passed={gk.check(cap1).passed}, rule={gk.check(cap1).rule_name}")

cap2 = ContextCapsule(source='clipboard', clipboard_text='my secret', foreground_app='1password.exe')
print(f"1Password: passed={gk.check(cap2).passed}, reason={gk.check(cap2).blocked_reason}")

cap3 = ContextCapsule(source='clipboard', clipboard_text='random text', foreground_app='notepad.exe')
print(f"Random: passed={gk.check(cap3).passed}, reason={gk.check(cap3).blocked_reason}")
