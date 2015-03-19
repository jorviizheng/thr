from tornado.gen import coroutine
from tornado.web import RequestHandler, Application, url
import tornadis

from thr.http2redis.rules import Rules
from thr.http2redis import HTTPExchange


redis_pool = tornadis.ClientPool()


class Handler(RequestHandler):

    @coroutine
    def get(self):
        exchange = HTTPExchange(self.request)
        Rules.execute(exchange)
        if 'status_code' in exchange.response:
            self.set_status(exchange.response['status_code'])
        else:
            redis = yield redis_pool.get_connected_client()
            yield redis.call('LPUSH', exchange.queue, exchange.request.path)


def make_app():
    return Application([
        url(r"/.*", Handler),
    ])


def main():
    print("Main")
