#!/usr/bin/env python3.5
import os
import logging
import asyncio
from weakref import WeakSet
from concurrent.futures import ProcessPoolExecutor
from time import sleep

import aiohttp.web
from aiohttp.http_websocket import WSCloseCode
from aiohttp.web_runner import GracefulExit


HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))

MESSAGE_MAX_SIZE = int(os.getenv('MESSAGE_MAX_SIZE', 20))
FIBO_MAX_N = int(os.getenv('FIBO_MAX_N', 10 ** 12))
FIBO_MAX_WORKERS = int(os.getenv('FIBO_MAX_WORKERS', 4))
TIMEOUT = int(os.getenv('TIMEOUT', 0))


class ErrorResult(Exception):
    error = 'some error occurred'

    def __init__(self, error):
        super().__init__(error)
        self.error = error


def fibo(n):
    if n == 42:
        raise Exception('Debug Exception')
    if FIBO_MAX_N and n > FIBO_MAX_N:
        raise ErrorResult('must be less than or equal %s ' % FIBO_MAX_N)

    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a


def sleep_func(message):
    seconds = -int(message)
    logging.info('sleeping %s', seconds)
    sleep(seconds)
    return 'waked up'


def get_fibo(message):
    import signal
    logging.debug('get_fibo %s start', message)
    try:
        if message.startswith('-'):
            return sleep_func(message)
        if message and not message.isdigit():
            raise ErrorResult('not integer')
        return fibo(int(message or 0))
    finally:
        print(signal.getsignal(signal.SIGINT))
        logging.debug('get_fibo %s stop', message)


class WSTaskExecutorHandler:
    def __init__(self, executor, target):
        self.executor = executor
        self.target = target
        self.websockets = WeakSet()

    async def __call__(self, request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        print('add', id(ws))
        request.app['websockets'].add(ws)
        print('add', ws)
        try:
            async for msg in ws:
                await self._handle_msg(ws, msg)
        finally:
            print('discard', id(ws))
            request.app['websockets'].discard(ws)
        return ws

    async def _handle_msg(self, ws, msg):
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
            response_data = await self._get_response(msg.data.strip())
            await ws.send_json(response_data)
        except asyncio.futures.TimeoutError:
            await ws.close(
                code=WSCloseCode.TRY_AGAIN_LATER,
                message='TRY_AGAIN_LATER',
            )
        except asyncio.CancelledError as e:
            await ws.close(
                code=WSCloseCode.GOING_AWAY,
                message='GOING_AWAY',
            )
        except Exception as e:
            logging.exception('INTERNAL_ERROR %s', e)
            await ws.close(
                code=WSCloseCode.INTERNAL_ERROR,
                message='INTERNAL_ERROR',
            )

    async def _get_response(self, message):
        loop = asyncio.get_event_loop()
        try:
            result_future = loop.run_in_executor(
                self.executor, get_fibo, message,
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


class GracefulShutdownWSApplication(aiohttp.web.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['websockets'] = WeakSet()

        async def on_shutdown(app):
            print('shutdown websockets')
            try:
                for ws in set(app['websockets']):
                    print('close', id(ws))
                    await ws.close(
                        code=WSCloseCode.GOING_AWAY,
                        message='SERVICE_RESTART',
                    )
            except BaseException as e:
                logging.error('GracefulShutdownWSApplication error', e)
            finally:
                raise GracefulExit('GracefulShutdownWSApplication')

        self.on_shutdown.append(on_shutdown)


def main():
    loop = asyncio.get_event_loop()

    app = GracefulShutdownWSApplication(loop=loop)

    ws_fibo_handler = WSTaskExecutorHandler(ProcessPoolExecutor(), get_fibo)
    app.router.add_route('GET', '/fibo', ws_fibo_handler)

    aiohttp.web.run_app(app, host=HOST, port=PORT, handle_signals=False)


if __name__ == '__main__':
    logging.root.setLevel(logging.DEBUG)
    logging.getLogger("asyncio").setLevel(logging.DEBUG)
    main()
