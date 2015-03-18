from tornado.web import RequestHandler, Application, url
from thr.http2redis.rules import Rules
from thr.http2redis import Exchange


class Handler(RequestHandler):

    def get(self):
        exchange = Exchange(self.request)
        Rules.execute(exchange)
        if 'status_code' in exchange.response:
            self.set_status(exchange.response['status_code'])
        self.write("Hello, world")


def make_app():
    return Application([
        url(r"/.*", Handler),
    ])


def main():
    print("Main")
