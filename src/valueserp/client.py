"""Provides search clients for accessing the APIs.

Currently, only Google is supported by VALUE SERP.
"""

__all__ = ["GoogleClient"]

import json
from types import TracebackType
from typing import Any, Dict, Optional, Union, Mapping
from typing_extensions import Self

import httpx

from valueserp import const
import valueserp.exceptions
from valueserp.serp import WebSERP
from valueserp.credentials import Credentials


class GoogleClient:
    """The primary interface for interacting with Google via VALUE SERP.

    Args:
        credentials: An initialized :class:`valueserp.Credentials` object.

    Attributes:
        credentials: An initialized :class:`valueserp.Credentials` object.
    """

    def __init__(self, credentials: Credentials, **kwargs):
        self.credentials = credentials
        transport = httpx.HTTPTransport(retries=kwargs.get("retries", 3))
        self._session = httpx.Client(
            base_url=const.ENDPOINT,
            params={"api_key": self.credentials.api_key},
            transport=transport,
            timeout=kwargs.get("timeout", 5.0),
        )

    def search(self, params: Dict[str, Any]) -> Mapping[str, Any]:
        """Conducts a generic search with the API and returns the response.

        Args:
            params: Parameters to send to the API with the request.

        Returns:
            The API response as a dict parsed from JSON.
        """
        response = self._request(const.API_PATH["search"], params=params)
        return json.loads(response)

    def web_search(
        self,
        query: str,
        location: Union[str, "valueserp.Location", None] = None,
        site: Optional[str] = None,
        **kwargs,
    ) -> WebSERP:
        """Makes a web search.

        Any `custom parameters`_ can be added as keyword arguments and will be
        passed directly to the API.

        Args:
            query: The query to search in Google.
            location: The location to use for the search in Google.
            site: Add a domain to use a site: search

        Returns:
            A :class:`~valueserp.serp.web.WebSERP` object containing the API
            response.

        .. _custom parameters: https://www.valueserp.com/docs/search-api/searches/google/search#googleSearchParameters
        """
        if site:
            query = f"site:{site} {query}"

        search_params = {
            "q": query,
            "location": location,
        }
        search_params.update(kwargs)
        response = self.search(params=search_params)

        return WebSERP(response)

    def _request(
        self,
        path: str,
        request_type: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Makes a request to the VALUE SERP API.

        Args:
            path: The API path to request. This must start with a '/' character.
            request_type:
                The type of HTTP request to send, such as 'GET' or 'POST'.
            params: Parameters to attach to the request as query strings.
            headers: Headers to provide with the request.
            data: JSON data to send along with the request.

        Returns:
            The API response body.

        Raises:
            APIError: The API responded with an error.
        """
        try:
            res = self._session.request(
                request_type, path, params=params, headers=headers, json=data
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            raw_json = e.response.json()
            message = raw_json["request_info"].get(
                "message", "No additional information."
            )
            raise valueserp.exceptions.APIError(
                f"VALUE SERP API responded with status {status_code}: {message}"
            ) from e
        except httpx.ConnectError as e:
            raise valueserp.exceptions.ConnectionError() from e
        except httpx.TimeoutException as e:
            raise valueserp.exceptions.Timeout() from e
        except httpx.RequestError as e:
            raise valueserp.exceptions.VSException("An unknown error occurred.") from e

        return res.text

    def close(self) -> None:
        """Closes the HTTP session."""
        self._session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Closes the client."""
        self.close()
