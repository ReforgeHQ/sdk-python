import sdk_reforge


def app(environ, start_response):
    output = f"value of 'test.config' is {sdk_reforge.get_client().config_client().get('test.config')}".encode()
    start_response(
        "200 OK", [("Content-Type", "text/plain"), ("Content-Length", str(len(output)))]
    )
    return iter([output])
