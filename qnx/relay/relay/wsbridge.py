#!/usr/bin/env python3
"""WebSocket -> 127.0.0.1:22 bridge.

The hosting platform terminates TLS and forwards wss:// to $PORT as plain ws://.
Each WS connection gets its own TCP connection to the container's sshd, so the
QNX reverse tunnel and a client's ProxyJump can be open simultaneously.
"""
import asyncio
import os
import sys

import websockets

TARGET_HOST = os.environ.get("TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "22"))


async def handler(ws):
    try:
        reader, writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except OSError as exc:
        print(f"sshd not reachable: {exc}", file=sys.stderr, flush=True)
        await ws.close(code=1011, reason="sshd unavailable")
        return

    peer = getattr(ws, "remote_address", None)
    print(f"open {peer}", file=sys.stderr, flush=True)

    async def ws_to_tcp():
        async for msg in ws:
            writer.write(msg.encode() if isinstance(msg, str) else msg)
            await writer.drain()

    async def tcp_to_ws():
        while True:
            data = await reader.read(65536)
            if not data:
                return
            await ws.send(data)

    pumps = {
        asyncio.create_task(ws_to_tcp()),
        asyncio.create_task(tcp_to_ws()),
    }
    try:
        done, pending = await asyncio.wait(
            pumps, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        results = await asyncio.gather(*pumps, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) and not isinstance(
                result, asyncio.CancelledError
            ):
                print(
                    f"closed {peer}: {type(result).__name__}",
                    file=sys.stderr,
                    flush=True,
                )
                break
    finally:
        for task in pumps:
            if not task.done():
                task.cancel()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass


async def main():
    port = int(os.environ.get("PORT", "8080"))
    # ping_interval keeps Railway's edge from idling the socket out.
    async with websockets.serve(
        handler, "0.0.0.0", port,
        ping_interval=20,
        ping_timeout=60,
        max_size=1 << 20,
        max_queue=16,
        compression=None,
    ):
        print(f"ws bridge listening on :{port}", file=sys.stderr, flush=True)
        await asyncio.Future()


asyncio.run(main())
