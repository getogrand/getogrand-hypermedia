from gevent import monkey

monkey.patch_all()

wsgi_app = "getogrand_hypermedia.wsgi"
bind = ["0.0.0.0:8000"]
workers = 1
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
preload_app = True
keepalive = 5
worker_class = "gevent"
