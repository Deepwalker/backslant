import sys
import os.path as op
import backslant
import asyncio
from aiohttp import web
sys.meta_path.insert(0, backslant.PymlFinder(op.dirname(__file__), hook="bsviews"))
from bsviews.templates import index


@asyncio.coroutine
def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = ''.join(index.render(title=name))
    return web.Response(body=text.encode('utf-8'))


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/{name}', handle)

    srv = yield from loop.create_server(app.make_handler(),
                                        '127.0.0.1', 8080)
    print("Server started at http://127.0.0.1:8080")
    return srv

print('start...')
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass