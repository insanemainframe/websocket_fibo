#!/usr/bin/env python3.5
import asyncio
import os
import sys

import aiohttp
from aiohttp.http_websocket import WSCloseCode
from aioconsole import ainput, aprint


HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))


async def user_interaction(ws):
    cmd = await ainput(">>> ")
    await ws.send_str(cmd)


async def main():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            'http://%s:%s/fibo' % (HOST, PORT)
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
            reason = 'Abnormal Closure'
        else:
            reason = WSCloseCode(ws.close_code).name
        await aprint('closed: %s' % reason)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
