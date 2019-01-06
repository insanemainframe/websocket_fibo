#!/usr/bin/env python3.5
import asyncio
import os
import sys

import aiohttp
from aiohttp.http_websocket import WSCloseCode
from aioconsole import ainput, aprint


async def user_interaction(ws):
    cmd = await ainput(">>> ")
    if cmd == 'q':
        await ws.close()
    else:
        await ws.send_str(cmd)


async def main():
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            'http://%s:%s/fibo' % (host, port)
        ) as ws:
            await ws.send_str(sys.argv[1] if len(sys.argv) > 1 else'')
            async for msg in ws:
                if msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
                await aprint(msg.json())
                await user_interaction(ws)
        if ws.close_code == 1006:
            await aprint('Abnormal Closure')
        else:
            await aprint('closed: ', WSCloseCode(ws.close_code))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
