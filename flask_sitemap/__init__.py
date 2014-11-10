# -*- coding: utf-8 -*-
#
# This file is part of Flask-Sitemap
# Copyright (C) 2014 CERN.
#
# Flask-Sitemap is free software; you can redistribute it and/or modify
# it under the terms of the Revised BSD License; see LICENSE file for
# more details.

"""
Flask-Sitemap generates an application sitemap.xml.

Initialization of the extension:

>>> from flask import Flask
>>> from flask_sitemap import Sitemap
>>> app = Flask('myapp')
>>> ext = Sitemap(app=app)

or alternatively using the factory pattern:

>>> app = Flask('myapp')
>>> ext = Sitemap()
>>> ext.init_app(app)
"""

from __future__ import absolute_import

import sys

from collections import Mapping
from flask import current_app, request, Blueprint, render_template, url_for

from . import config
from .version import __version__

# PY2/3 compatibility
if sys.version_info[0] == 3:
    string_types = str,
else:
    string_types = basestring,


class Sitemap(object):

    """Flask extension implementation."""

    def __init__(self, app=None):
        """Initialize login callback."""
        self.url_generators = [self._routes_without_params]

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize a Flask application."""
        self.app = app
        # Follow the Flask guidelines on usage of app.extensions
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        if 'sitemap' in app.extensions:
            raise RuntimeError("Flask application already initialized")
        app.extensions['sitemap'] = self

        # Set default configuration
        for k in dir(config):
            if k.startswith('SITEMAP_'):
                self.app.config.setdefault(k, getattr(config, k))

        # Create and register Blueprint
        if app.config.get('SITEMAP_BLUEPRINT'):
            # Add custom `template_folder`
            self.blueprint = Blueprint(app.config.get('SITEMAP_BLUEPRINT'),
                                       __name__, template_folder='templates')

            self.blueprint.add_url_rule(
                app.config.get('SITEMAP_ENDPOINT_URL'),
                'sitemap',
                self.sitemap
            )
            app.register_blueprint(
                self.blueprint,
                url_prefix=app.config.get('SITEMAP_BLUEPRINT_URL_PREFIX')
            )

    def sitemap(self):
        """Generate sitemap.xml."""
        return render_template('flask_sitemap/sitemap.xml',
                               urlset=self._generate_all_urls())

    def register_generator(self, generator):
        """Register an URL generator.

        The function should return an iterable of URL paths or
        ``(endpoint, values)`` tuples to be used as
        ``url_for(endpoint, **values)``.

        :return: the original generator function
        """
        self.url_generators.append(generator)
        # Allow use as a decorator
        return generator

    def _routes_without_params(self):
        if self.app.config['SITEMAP_INCLUDE_RULES_WITHOUT_PARAMS']:
            for rule in self.app.url_map.iter_rules():
                if 'GET' in rule.methods and len(rule.arguments) == 0:
                    yield rule.endpoint, {}

    def _generate_all_urls(self):
        """Run all generators and yield (url, enpoint) tuples."""
        ignore = set(self.app.config['SITEMAP_IGNORE_ENDPOINTS'] or [])
        kwargs = dict(
            _external=True,
            _scheme=self.app.config.get('SITEMAP_URL_SCHEME')
        )
        # A request context is required to use url_for
        with self.app.test_request_context():
            for generator in self.url_generators:
                for generated in generator():
                    result = {}
                    if isinstance(generated, string_types):
                        result['loc'] = generated
                    else:
                        if isinstance(generated, Mapping):
                            values = generated
                            # The endpoint defaults to the name of the
                            # generator function, just like with Flask views.
                            endpoint = generator.__name__
                        else:
                            # Assume a tuple.
                            endpoint, values = generated[0:2]
                            # Get optional lastmod, changefreq, and priority
                            left = generated[2:]
                            for key in ['lastmod', 'changefreq', 'priority']:
                                if len(left) == 0:
                                    break
                                result[key] = left[0]
                                left = left[1:]

                        # Check if the endpoint should be skipped
                        if endpoint in ignore:
                            continue

                        values.update(kwargs)
                        result['loc'] = url_for(endpoint, **values)
                    yield result


__all__ = ('Sitemap', '__version__')
