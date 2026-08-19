from .base import *  # noqa: F401,F403

DEBUG = False

# Off until a domain + TLS reverse proxy is in front of this deploy — with no
# certificate, forcing HTTPS redirects/secure cookies would make the site
# unreachable over plain HTTP. Flip DJANGO_USE_SSL=True once TLS is in place.
USE_SSL = env.bool("DJANGO_USE_SSL", default=True)  # noqa: F405

SESSION_COOKIE_SECURE = USE_SSL
CSRF_COOKIE_SECURE = USE_SSL
SECURE_SSL_REDIRECT = USE_SSL
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 518400 if USE_SSL else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_SSL
SECURE_HSTS_PRELOAD = USE_SSL

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
