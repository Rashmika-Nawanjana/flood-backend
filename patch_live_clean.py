import re
with open('app/ws/live.py', 'r') as f:
    content = f.read()

# find everything between _event_payload and _kafka_consumer_loop
start_idx = content.find('def _event_payload')
end_idx = content.find('async def _kafka_consumer_loop')

if start_idx != -1 and end_idx != -1:
    end_of_func = content.find('\n\n\n', start_idx) + 3
    new_content = content[:end_of_func] + content[end_idx:]
    with open('app/ws/live.py', 'w') as f:
        f.write(new_content)
        print("Cleaned!")
