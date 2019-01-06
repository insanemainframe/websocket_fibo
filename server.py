#!/usr/bin/env python3.5
import os
import logging
import asyncio
import signal
from weakref import WeakSet
from concurrent.futures import ProcessPoolExecutor

import aiohttp.web
from aiohttp.http_websocket import WSCloseCode
from aiohttp.web_runner import GracefulExit


HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))

MESSAGE_MAX_SIZE = int(os.getenv('MESSAGE_MAX_SIZE', 20))
FIBO_MAX_N = int(os.getenv('FIBO_MAX_N', 10 ** 12))
FIBO_MAX_WORKERS = int(os.getenv('FIBO_MAX_WORKERS', 4))
FIBO_TIMEOUT = int(os.getenv('FIBO_MAX_WORKERS', 0))


class ErrorResult(Exception):
    error = 'some error occurred'

    def __init__(self, error):
        super().__init__(error)
        self.error = error


def fibo(n):
    if n == 42:
        raise Exception('debug error')
    if FIBO_MAX_N and n > FIBO_MAX_N:
        raise ErrorResult('must be less than or equal %s ' % FIBO_MAX_N)

    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a


def get_fibo(message):
    logging.debug('get_fibo %s start', message)
    try:
        if message.startswith('-'):
            import time
            time.sleep(-int(message))
            return 'swakeup'
        if message and not message.isdigit():
            raise ErrorResult('not integer')
        return fibo(int(message or 0))
    finally:
        logging.debug('get_fibo %s stop', message)


class WSTaskExecutorHandler:
    def __init__(self, target):
        self.executor = ProcessPoolExecutor()
        self.target = target
        self.websockets = WeakSet()

    async def __call__(self, request):
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
                response_data = await self._handle_message(msg.data.strip())
                await ws.send_json(response_data)
            except asyncio.futures.TimeoutError:
                await ws.close(
                    code=WSCloseCode.TRY_AGAIN_LATER,
                    message='TRY_AGAIN_LATER',
                )
            except Exception as e:
                logging.exception('INTERNAL_ERROR', e)
                await ws.close(
                    code=WSCloseCode.INTERNAL_ERROR,
                    message='INTERNAL_ERROR',
                )
        return ws

    async def _handle_message(self, message):
        loop = asyncio.get_event_loop()
        try:
            result_future = loop.run_in_executor(
                self.executor, get_fibo, message,
            )
            result = await asyncio.wait_for(
                result_future,
                FIBO_TIMEOUT or None,
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

    def shutdown(self, loop):
        logging.info('waiting executor shutdown')
        # self.executor.shutdown(True)
        logging.info('executor shuted down')
        raise GracefulExit(self.__class__.__name__)


def main():
    loop = asyncio.get_event_loop()
    ws_fibo_handler = WSTaskExecutorHandler(get_fibo)
    loop.add_signal_handler(signal.SIGINT, ws_fibo_handler.shutdown, loop)

    app = aiohttp.web.Application(loop=loop)
    app.router.add_route('GET', '/fibo', ws_fibo_handler)

    aiohttp.web.run_app(app, host=HOST, port=PORT, handle_signals=False)
    loop.close()


if __name__ == '__main__':
    logging.root.setLevel(logging.DEBUG)
    logging.getLogger("asyncio").setLevel(logging.DEBUG)
    main()
