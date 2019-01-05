#!/usr/bin/env python3.5

import asyncio
import os

import aiohttp


async def main():
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    session = aiohttp.ClientSession()
    async with session.ws_connect('http://%s:%s/fibo' % (host, port)) as ws:

        await prompt_and_send(ws)
        async for msg in ws:
            print('Message received from server:', msg)
            await prompt_and_send(ws)

            if msg.type in (aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR):
                break


async def prompt_and_send(ws):
    new_msg_to_send = input('Type a message to send to the server: ')
    if new_msg_to_send == 'exit':
        print('Exiting!')
        raise SystemExit(0)
    await ws.send_str(new_msg_to_send)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
