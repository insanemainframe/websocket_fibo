#!/usr/bin/env python3.5
import os
import logging
import asyncio
from concurrent.futures import ProcessPoolExecutor

import aiohttp.web
from aiohttp.http_websocket import WSCloseCode


HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))

MESSAGE_MAX_SIZE = int(os.getenv('MESSAGE_MAX_SIZE', 20))
FIBO_MAX_N = int(os.getenv('FIBO_MAX_N', 10 ** 12))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', 4))
TIMEOUT = int(os.getenv('TIMEOUT', 0))
ERROR_NUMBER = int(os.getenv('ERROR_NUMBER', 42))


class ErrorResult(Exception):
    """
    Error returning to client
    """
    error = 'some error occurred'

    def __init__(self, error):
        super().__init__(error)
        self.error = error


def fibo(n):
    """
    Returns Fibonacci numbers or raise exception for magic ERROR_NUMBER
    """
    if n == ERROR_NUMBER:
        raise Exception('Debug Exception %d' % ERROR_NUMBER)
    if FIBO_MAX_N and n > FIBO_MAX_N:
        raise ErrorResult('must be less than or equal %s ' % FIBO_MAX_N)

    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a


def get_fibo_result(message):
    """
    Fibonacci numbers task
    """
    if message and not message.isdigit():
        raise ErrorResult('must be positive integer')
    return fibo(int(message or 0))


class WSTaskExecutorHandler:
    """
    Asynchronous task websocket handler
    """

    def __init__(self, executor, target):
        assert callable(target)
        self.executor = executor
        self.target = target

    async def __call__(self, request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            await self._handle_msg(ws, msg)
        return ws

    async def _handle_msg(self, ws, msg):
        """
        Handle client message and close connection, if necccessary
        """
        logging.debug(msg)
        if msg.type != aiohttp.WSMsgType.TEXT:
            await ws.close(
                code=WSCloseCode.UNSUPPORTED_DATA,
            )
        if len(msg.data) > MESSAGE_MAX_SIZE:
            await ws.close(
                code=WSCloseCode.MESSAGE_TOO_BIG,
            )
        if msg.data == 'q':
            await ws.close()
            return
        try:
            response_data = await self._run_task(msg.data.strip())
            await ws.send_json(response_data)
        except asyncio.futures.TimeoutError:
            await ws.close(
                code=WSCloseCode.TRY_AGAIN_LATER,
            )
        except Exception as e:
            logging.exception('INTERNAL_ERROR %s', e)
            await ws.close(
                code=WSCloseCode.INTERNAL_ERROR,
            )

    async def _run_task(self, message):
        """
        Run asynchronous task in executor and return result dict
        """
        loop = asyncio.get_event_loop()
        try:
            result_future = loop.run_in_executor(
                self.executor, get_fibo_result, message,
            )
            result = await asyncio.wait_for(
                result_future,
                TIMEOUT or None,
                loop=loop
            )
            return {
                'error': None,
                'result': result,
            }
        except ErrorResult as e:
            return {
                'error': e.error,
                'result': None,
            }


def main():
    loop = asyncio.get_event_loop()
    app = aiohttp.web.Application(loop=loop)

    executor = ProcessPoolExecutor(max_workers=MAX_WORKERS)

    ws_fibo_handler = WSTaskExecutorHandler(executor, get_fibo_result)
    app.router.add_route('GET', '/fibo', ws_fibo_handler)

    aiohttp.web.run_app(app, host=HOST, port=PORT, handle_signals=True)


if __name__ == '__main__':
    logging.root.setLevel(logging.DEBUG)
    main()
