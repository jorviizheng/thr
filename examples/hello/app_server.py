from wsgiref.simple_server import make_server


def hello_world_app(environ, start_response):
    start_response(status='200 OK', headers=[('Content-type', 'text/plain')])
    return ["Hello World\n"]

HTTP_PORT = 9999
print("Serving app on http://localhost:{}".format(HTTP_PORT))
make_server('', HTTP_PORT, hello_world_app).serve_forever()
