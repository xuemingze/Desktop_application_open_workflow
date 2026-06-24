import asyncio
import json
import websockets

async def test():
    uri = 'ws://127.0.0.1:12393/client-ws'
    try:
        async with websockets.connect(uri, ping_interval=None, open_timeout=10) as ws:
            msg = {
                'type': 'text-input',
                'content': '请用 get_system_info 工具查看一下系统信息，然后用中文回复我'
            }
            await ws.send(json.dumps(msg))
            print('SENT:', json.dumps(msg))
            
            for i in range(15):
                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    print(f'RECV [{i}]:', resp[:300] if len(resp) > 300 else resp)
                    # Stop if we get a full-text (final response)
                    try:
                        data = json.loads(resp)
                        if data.get('type') == 'full-text':
                            print('=== FINAL RESPONSE RECEIVED ===')
                            break
                    except:
                        pass
                except asyncio.TimeoutError:
                    print(f'timeout {i}')
                    break
    except Exception as e:
        print('ERROR:', e)

asyncio.run(test())
