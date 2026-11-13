"""Exercise real hosted WebSocket sessions; report server cgroup memory peaks.

Run inside the dashboard container while its normal server is running. Unlike
AppTest, this exercises the shared API/UI process and concurrent browser state.
"""

import asyncio
import json
from pathlib import Path

from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.asyncio.client import connect


async def main():
    connections = []
    samples = []
    try:
        for _ in range(6):
            connection = await connect(
                "ws://127.0.0.1:8501/_stcore/stream",
                subprotocols=["streamlit"], open_timeout=10,
            )
            connections.append(connection)
            for _ in range(3):
                request = BackMsg()
                request.rerun_script.query_string = ""
                await connection.send(request.SerializeToString())
                while True:
                    payload = await asyncio.wait_for(connection.recv(), 30)
                    if payload is None:
                        raise RuntimeError("Dashboard session disconnected unexpectedly")
                    message = ForwardMsg.FromString(payload)
                    if (message.HasField("delta") and message.delta.HasField("new_element")
                            and message.delta.new_element.HasField("exception")):
                        raise RuntimeError(message.delta.new_element.exception.message)
                    if message.HasField("script_finished"):
                        break
                samples.append(int(Path("/sys/fs/cgroup/memory.current").read_text()))
        peak = int(Path("/sys/fs/cgroup/memory.peak").read_text())
        events = dict(
            line.split() for line in Path("/sys/fs/cgroup/memory.events").read_text().splitlines()
        )
        assert int(events["oom_kill"]) == 0, events
        # Leave headroom for API requests and route geometry on a 512 MiB host.
        assert max(samples) < 420 * 1024**2, samples
        print(json.dumps({"sessions": 6, "renders": len(samples),
                          "resident_cgroup_mib": [round(x / 1024**2, 1) for x in samples],
                          "peak_cgroup_mib": round(peak / 1024**2, 1), "events": events}))
    finally:
        for connection in connections:
            await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
