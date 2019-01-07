Fibonacci numbers websocket example
=========================

Using Python3.5, [aiohttp](http://aiohttp.readthedocs.io/en/stable/index.html) and [concurrent.futures.ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor)


Install
------------------------------

install dependencies:

	pip install -r requirements.txt


Run
------------------------------

run server:
	
	python server.py

run client:

	python test_client.py

run yet another client, with heavyweight job:

	python test_client.py 1234567890