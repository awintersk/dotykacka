"""Module for managing API Requests."""
__version__ = "1.2"

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote_plus as url_encode

import requests
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import ValidationError

LOG_ORIGIN = __name__
_logger = logging.getLogger(LOG_ORIGIN)


# pylint: disable=R0902
class APIRequest(models.Model):
    """API Requests manager."""

    _name = 'api_manager.request'
    _rec_name = 'record_path'
    _description = "Request"

    _headers = {}
    _query_args = {}
    _auth_method = None
    _data = ""
    _query = ""
    _parametrized = False
    _cookies = None

    response = None
    error = None
    message = None
    status_code = None
    success = False

    @property
    def headers(self):
        """Getter for _headers."""
        return self._headers

    @property
    def cookies(self):
        """Getter for _cookies."""
        return self._cookies

    @property
    def data(self):
        """Getter for _data."""
        return self._data

    name = fields.Char(store=True)

    @api.depends('provider', 'method')
    def _compute_display_name(self):
        """Compute full url."""
        for record in self:
            name = f"[{record.provider.internal_reference}][{record.method}] {record.name}"
            record.display_name = name

    display_name = fields.Char("Name", compute="_compute_display_name")
    url_path = fields.Char("Request URL Path", required=True)
    provider = fields.Many2one(
        'api_manager.provider', string='API Provider', ondelete='restrict', required=True
    )
    record_path = fields.Char(compute='_compute_record_path')
    method = fields.Selection(
        selection=[
            ('GET', "GET"),
            ('HEAD', "HEAD"),
            ('POST', "POST"),
            ('PUT', "PUT"),
            ('DELETE', "DELETE"),
            ('CONNECT', "CONNECT"),
            ('OPTIONS', "OPTIONS"),
            ('TRACE', "TRACE"),
            ('PATH', "PATH"),
            ('PATCH', "PATCH"),
        ],
        required=True,
    )
    payload = fields.Text(
        "Data Payload",
        store=True,
        help=(
            "JSON data send with request. This will always override passed data to "
            "'send_request' method! For example custom code in ir.cron"
        ),
    )
    content_type = fields.Selection(
        [
            ('application/pdf', 'application/pdf'),
            ('application/javascript', 'application/javascript'),
            ('application/octet-stream', 'application/octet-stream'),
            ('application/ogg', 'application/ogg'),
            ('application/xhtml+xml', 'application/xhtml+xml'),
            ('application/json', 'application/json'),
            ('application/ld+json', 'application/ld+json'),
            ('application/xml', 'application/xml'),
            ('application/zip', 'application/zip'),
            ('application/x-www-form-urlencoded', 'application/x-www-form-urlencoded'),
            ('audio/mpeg', 'audio/mpeg'),
            ('audio/x-wav', 'audio/x-wav'),
            ('image/gif', 'image/gif'),
            ('image/jpeg', 'image/jpeg'),
            ('image/png', 'image/png'),
            ('image/tiff', 'image/tiff'),
            ('image/svg+xml', 'image/svg+xml'),
            ('multipart/mixed', 'multipart/mixed'),
            ('multipart/alternative', 'multipart/alternative'),
            ('RELATED (USING BY MHTML (HTML MAIL).)', 'multipart/related'),
            ('multipart/form-data', 'multipart/form-data'),
            ('text/css', 'text/css'),
            ('text/csv', 'text/csv'),
            ('text/html', 'text/html'),
            ('text/plain', 'text/plain'),
            ('text/xml', 'text/xml'),
            ('video/mpeg', 'video/mpeg'),
            ('video/mp4', 'video/mp4'),
            ('video/quicktime', 'video/quicktime'),
            ('video/webm', 'video/webm'),
        ],
    )
    parametrized_url = fields.Boolean("Parametrized", compute='_compute_parametrized', store=True)

    @api.depends('provider', 'name')
    def _compute_record_path(self) -> None:
        """Compute nested name for record from provider name."""
        for request in self:
            request.record_path = f"{request.provider.name} / {request.name}"

    @api.depends('url_path')
    def _compute_parametrized(self) -> None:
        """Compute nested name for record from provider name."""
        for request in self:
            request.parametrized_url = bool(re.search(r'{[^}]*}', request.url_path))

    @api.constrains('payload')
    def _check_valid_json(self) -> None:
        """
        Validate user input for field :class:`APIRequest`.payload.

        Raises :py:exc:`ValidationError`

        :raises ValidationError: If string is not valid JSON
        """
        for request in self:
            if request.payload:
                try:
                    json.loads(request.payload)
                except ValueError as exc:
                    _logger.error("Payload is not valid JSON!")
                    raise ValidationError(_("Payload is not valid JSON!")) from exc

    # --- PREPARE REQUEST --- #

    def _set_authentication(self) -> Optional[requests.auth.AuthBase]:
        """Return authentication method or set appropriate headers."""
        auth_method = self.provider.authentication_method
        if auth_method == 'basic':
            vals = self._get_auth_kv(['username', 'password'])
            return requests.auth.HTTPBasicAuth(vals[0], vals[1])
        if auth_method == 'digest':
            vals = self._get_auth_kv(['username', 'password'])
            return requests.auth.HTTPDigestAuth(vals[0], vals[1])
        if auth_method == 'bearer_token':
            self._headers['Authorization'] = 'Bearer ' + self._get_auth_kv(['token'])[0]
        if auth_method == 'api_token' and self.provider.token_method == 'header':
            self._headers[self.provider.key] = self._get_auth_kv(['value'])[0]
        if auth_method == 'api_token' and self.provider.token_method == 'query_arg':
            self._query_args[self.provider.key] = self._get_auth_kv(['value'])[0]
        return None

    def _get_auth_kv(self, values: list) -> list:
        """
        Get authentication values for request based on company and provider.

        Authentication values such a token, username, password are stored in model api_manager.request_parameter.
        In case it doesn't exist, return default value stored on provider model.

        :param values: list of authentication fields

        :return: list of credentials
        """
        res = []
        for val in values:
            rel_kv = self.env['api_manager.request_parameter'].search(
                [
                    ('provider', '=', self.provider.id),
                    ('key', '=', val),
                    ('company_id', '=', self.env.company.id),
                ]
            )
            if rel_kv:
                if not rel_kv.value:
                    msg = f"Value is not set for key/value {rel_kv.id}"
                    raise ValidationError(_(msg))
                res.append(rel_kv.value)
            else:
                res.append(getattr(self.provider, val))
        return res

    @staticmethod
    def _get_parametrized_query(query, params: Dict[str, str]) -> str:
        """
        Replace parameters in query path with dictionary data.

        :param query: Original query
        :param params: Data to replace 'key' with 'value' in query

        :return: Modified query
        """
        for key, value in params.items():
            query = re.sub(key, value, query)
        return query

    def _get_query_wth_args(self, query, args: Dict[str, str]) -> str:
        """
        Replace parameters in query path with dictionary data.

        :param query: Original query
        :param params: Data to replace 'key' with 'value' in query

        :return: Modified query
        """
        args = {**args, **self._query_args}
        for key, value in args.items():
            query += ("&" if self._parametrized else "?") + key + "=" + value
            self._parametrized = True
        return query

    def _get_payload(self, data: Union[Dict, List]) -> Union[dict, list]:
        """
        Prepare request payload data.

        :param data: Hardcoded data from caller
        :return: Union[Dict, List]
        """
        override = self.payload or "{}"
        payload = json.loads(override)
        if isinstance(data, list):  # pylint:disable=R1705
            payload_list = []
            for item in data:
                payload_list.append({**item, **payload})
            return payload_list
        else:
            return {**data, **payload}

    def _prepare_headers(self, headers: dict):
        """
        Prepare headers with content type and custom data.

        :param headers: Dictionary containing new headers
        """
        if not self._headers.get('Content-Type') and self.content_type:
            self._headers['Content-Type'] = self.content_type
        for key, value in headers.items():
            self._headers[key] = value

    def _prepare_url(self, params, args, encode=False):
        """
        Prepare url with new parameters and arguments data.

        :param params: Dictionary containing new parameters
        :param args: Dictionary containing new arguments
        :param args: Should url be encoded by basic library?
        """
        query = f"{self.provider.server_url}{self.url_path}"
        query = self._get_parametrized_query(query, params)
        query = self._get_query_wth_args(query, args)
        self._query = url_encode(query) if encode else query

    def get_request_data(self, **kwargs) -> Dict[str, Any]:
        """
        Prepare and return request data.

        :param kwargs: Request Data
        :keyword headers: Dict[str, str]: Headers
            |  See method `_prepare_headers`
        :keyword params: Dict[str, str]: Path parameters
            |  See method `_get_parametrized_query`
        :keyword args: Dict[str,str]: Query arguments
            |  See method `_get_query_wth_args`
        :keyword data: Union[Dict, List]: Request body
            |  See method `_get_payload`

        :return: Request data
        """
        self._auth_method = self._set_authentication()
        self._prepare_headers(kwargs.get('headers', {}))
        self._prepare_url(
            kwargs.get('params', {}), kwargs.get('args', {}), kwargs.get('urlsafe', False)
        )
        self._data = self._get_payload(kwargs.get('data', {}))
        data_key = 'json' if self.content_type == 'application/json' else 'data'
        request_args = {
            'method': self.method.lower(),
            'auth': self._auth_method,
            'headers': self._headers,
            'url': self._query,
            'cookies': self._cookies,
            data_key: self._data,
        }

        return request_args

    # --- PROCESS REQUEST --- #

    def _send_request(self, request_data: Dict[str, Any]):
        """
        Send request with prepared data.

        :param request_data: Request Data
        """
        with requests.Session() as session:
            retries = 5
            # This doesn't retry on status codes, only if request doesn't reach the server!
            retry = requests.adapters.Retry(
                total=retries, read=retries, connect=retries, backoff_factor=0.1
            )
            http_adapter = requests.adapters.HTTPAdapter(max_retries=retry)
            session.mount(self.provider.server_scheme, http_adapter)
            self.response = session.request(**request_data)
            self.message = self.response.text

    def send_request(self, **kwargs) -> Any:
        """
        Send request and return response.

        :param kwargs: Request Data
        :keyword headers: Dict[]: Dictionary containing new headers
        :keyword params: Dict[key, value]: Path parameters
            .. replace 'key' in query path with 'value'
        :keyword args: Dict[key,value]: Query arguments
            ..  add 'key'='value' to query arguments
        :keyword data: Union[Dict[], List]: Request body

        :return: True if request successful, else False
        """

        self.log_request(LOG_ORIGIN)
        request_data = self.get_request_data(**kwargs)
        try:
            self._send_request(request_data)
            self._set_status_code()
            self.success = self.status_code // 200 == 1
        except (requests.exceptions.HTTPError, requests.exceptions.Timeout):
            result = self._retry_request(**kwargs)
            if result is not None:
                # If no retry available return previous data
                return result
        except requests.exceptions.ConnectionError as error:
            # TODO - Connection issue - Store request in Queue and retry after some time.
            self._set_error(error)
        except requests.exceptions.RequestException as error:
            # Any other request error. Raise Exceptions manually after send_request call!
            self._set_error(error)

        return self._get_return_value(kwargs.get('return_type', 'success'))

    def _retry_request(self, **kwargs):
        """
        Retry request based on status code and available attempts.

        :keyword retry_on_error: bool: True if request should by retried
        :keyword attempt: int: Current retry attempt index.
        :keyword max_attempts: int: Maximum number of attempts to retry.
        :keyword retry_on_http_error: Tuple[int]: Maximum number of attempts to retry.
        :keyword backoff_factor: int: See:
            https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html.

        :return: None if request shouldn't be retried else see :func:`send_request`.
        """
        if not kwargs.get('retry_on_error', False):
            return None

        attempt = kwargs.get('attempt', 1)
        max_attempts = kwargs.get('max_attempts', 5)
        if attempt > max_attempts:
            return None
        whitelisted_codes = kwargs.get('retry_on_http_error', tuple(range(400, 600)))
        if self.status_code not in whitelisted_codes:
            return None

        backoff_factor = kwargs.get("backoff_factor", 1)
        time.sleep(backoff_factor * (2 ** (attempt - 1)))  # Wait before next retry
        kwargs["attempt"] = attempt + 1
        return self.send_request(**kwargs)

    # --- PROCESS RESPONSE --- #

    def _get_return_value(self, return_type):
        if return_type == 'decoded':
            return self.decode_response()
        return getattr(self, return_type, self.success) if self.success else False

    def _set_error(self, error):
        """Set Error with data from exception."""
        self.error = error.response
        self.message = str(error)

    def _set_status_code(self):
        """Set status code with response code if exists else False."""
        self.status_code = getattr(self.response, 'status_code', False)

    def decode_response(self) -> dict:
        """
        Return json response.

        :return: Dictionary representing JSON data or empty dict
        """
        try:
            return self.response.json()
        except json.decoder.JSONDecodeError:
            _logger.debug(
                "Response is not JSON: %s",
                {
                    "request_name": self.name,
                    "url": self._query,
                    "response": self.response.text,
                },
            )
        return {}

    def log_request(self, origin=None):
        """Log outgoing requests to api_manager.logger."""
        self.env['api_manager.logger'].with_user(SUPERUSER_ID).sudo().create(
            {
                'created_at': datetime.now(),
                'origin': origin or LOG_ORIGIN,
                'direction': "outgoing",
                'data': {
                    "headers": self._headers,
                    "cookies": self._cookies,
                    "data": self._data,
                },
            }
        )

    def clear(self):
        """Clear all cached data in current instance."""
        self._headers = {}
        self._query_args = {}
        self._auth_method = None
        self._data = ""
        self._query = ""
        self._parametrized = False
        self._cookies = None

        self.response = None
        self.error = None
        self.message = None
        self.status_code = None
        self.success = False
