from tornado import gen, ioloop, httpclient


@gen.coroutine
def make_requests():
    client = httpclient.AsyncHTTPClient()
    # Send 10 requests concurrently
    requests = [
        client.fetch('http://127.0.0.1:8888/', headers={
            'Foo': 'value_%s' % i
        }) for i in range(10)
    ]
    responses = yield requests  # Block until we've received all responses
    assert all(response.code == 200 for response in responses)


ioloop.IOLoop.current().run_sync(make_requests)
