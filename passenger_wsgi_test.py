# passenger_wsgi_test.py
# =============================================================
# MINIMAL test to verify Passenger is working at all.
# Rename this to passenger_wsgi.py to test, then restore original.
# =============================================================

import sys
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def application(environ, start_response):
    """Bare-bones WSGI app — no Django, no dependencies."""
    status = "200 OK"
    body = "Passenger is working!\n\n"
    body += "Python: {}.{}.{}\n".format(*sys.version_info[:3])
    body += "sys.executable: {}\n".format(sys.executable)
    body += "cwd: {}\n".format(os.getcwd())
    body += "__file__: {}\n".format(os.path.abspath(__file__))
    body += "Time: {}\n".format(datetime.datetime.now())
    body += "\nsys.path:\n"
    for p in sys.path:
        body += "  {}\n".format(p)
    body += "\nEnviron keys:\n"
    for k in sorted(environ.keys()):
        if k.startswith("PASSENGER") or k.startswith("SERVER") or k.startswith("PATH") or k == "DOCUMENT_ROOT":
            body += "  {} = {}\n".format(k, environ.get(k, ""))

    output = body.encode("utf-8")
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(output))),
    ]
    start_response(status, headers)
    return [output]

