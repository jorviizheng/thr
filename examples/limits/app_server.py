import time


def application(environ, start_response):
    time.sleep(1)
    data = "Hello World!\n"
    start_response(status='200 OK', headers=[
        ('Content-type', 'text/plain'),
        ('Content-length', str(len(data))),
    ])
    return [data]
