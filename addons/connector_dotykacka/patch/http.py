"""Monkeypatch of HTTP module."""
# pylint:disable=all
import json
import logging

from odoo.http import JsonRequest
from werkzeug import exceptions

_logger = logging.getLogger(__name__)


def patch_json_request():
    """Patch JsonRequest init method to handle array body."""

    def new_init(self, *args):  # pylint:disable=W0612
        super(JsonRequest, self).__init__(*args)
        self.params = {}
        request = self.httprequest.get_data().decode(self.httprequest.charset)

        # Read POST content or POST Form Data named "request"
        try:
            self.jsonrequest = json.loads(request)
        except ValueError:
            msg = 'Invalid JSON data: %r' % (request,)
            _logger.info('%s: %s', self.httprequest.path, msg)
            raise exceptions.BadRequest(msg)

        if isinstance(self.jsonrequest, list):  # Process array json
            self.jsonrequest = {'items': self.jsonrequest}
        self.params = dict(self.jsonrequest.get("params", {}))
        self.context = self.params.pop('context', dict(self.session.context))

    JsonRequest.__init__ = new_init
