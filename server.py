#!/usr/bin/env python3.5
import os
import logging
from functools import lru_cache
import asyncio

import aiohttp.web
from aiohttp.http_websocket import WSCloseCode

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))

FIBO_CACHE_SIZE = int(os.getenv('FIBO_CACHE_SIZE', 128))
FIBO_MAX_N = int(os.getenv('FIBO_MAX_N', 10 ** 6))
MESSAGE_MAX_SIZE = int(os.getenv('MESSAGE_MAX_SIZE', 11))


class ErrorResponse(Exception):
    error = 'ERROR'
    error_message = 'some error occurred'

    def __init__(self, error, error_message):
        self.error = error
        self.error_message = error_message


@lru_cache(maxsize=FIBO_CACHE_SIZE)
def fibo(n):
    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a


async def get_fibo(n):
    if FIBO_MAX_N and n > FIBO_MAX_N:
        raise ErrorResponse(
            error='VALUE_ERROR',
            error_message=(
                'integer must be less than or equal %s ' % FIBO_MAX_N
            ),
        )
    # for dev
    if n == 42:
        raise Exception('debug error')
    return fibo(n)


async def handle_message(message):
    if message and not message.isdigit():
        return {
            'error': 'TYPE_ERROR',
            'error_message': 'not integer',
            'result': None,
        }
    try:
        result = await get_fibo(int(message or 0))
        return {
            'error': None,
            'error_message': None,
            'result': result,
        }
    except ErrorResponse as e:
        return {
            'error': e.error,
            'error_message': e.error_message,
            'result': None,
        }


async def websocket_handler(request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        logging.debug(msg)
        if msg.type != aiohttp.WSMsgType.TEXT:
            await ws.close(
                code=WSCloseCode.UNSUPPORTED_DATA,
                message='UNSUPPORTED_DATA',
            )
        if len(msg.data) > MESSAGE_MAX_SIZE:
            await ws.close(
                code=WSCloseCode.MESSAGE_TOO_BIG,
                message='MESSAGE_TOO_BIG',
            )
        if msg.data == 'close':
            await ws.close()
        try:
            response_data = await handle_message(msg.data.strip())
            await ws.send_json(response_data)
        except Exception as e:
            logging.exception(e)
            await ws.close(
                code=WSCloseCode.INTERNAL_ERROR,
                message='INTERNAL_ERROR',
            )
    return ws


def main():
    loop = asyncio.get_event_loop()
    app = aiohttp.web.Application(loop=loop)
    app.router.add_route('GET', '/fibo', websocket_handler)
    aiohttp.web.run_app(app, host=HOST, port=PORT)


if __name__ == '__main__':
    logging.root.setLevel(logging.DEBUG)
    main()
