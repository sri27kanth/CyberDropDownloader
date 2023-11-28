from __future__ import annotations

from typing import TYPE_CHECKING

import browser_cookie3

from cyberdrop_dl.utils.dataclasses.supported_domains import SupportedDomains

if TYPE_CHECKING:
    from typing import Dict

    from cyberdrop_dl.managers.manager import Manager


# noinspection PyProtectedMember
def get_forum_cookies(manager: Manager, browser: str) -> None:
    """Get the cookies for the forums"""
    auth_args: Dict = manager.config_manager.authentication_data
    for forum in SupportedDomains.supported_forums:
        try:
            cookie = get_cookie(browser, forum)
            auth_args['Forums'][f'{SupportedDomains.supported_forums_map[forum]}_xf_user_cookie'] = cookie._cookies[forum]['/']['xf_user'].value
        except KeyError:
            try:
                cookie = get_cookie(browser, "www." + forum)
                auth_args['Forums'][f'{SupportedDomains.supported_forums_map[forum]}_xf_user_cookie'] = cookie._cookies["www." + forum]['/']['xf_user'].value
            except KeyError:
                pass

    manager.cache_manager.save("browser", browser)


def get_cookie(browser: str, domain: str):
    """Get the cookies for a specific domain"""
    if browser == 'chrome':
        cookie = browser_cookie3.chrome(domain_name=domain)
    elif browser == 'firefox':
        cookie = browser_cookie3.firefox(domain_name=domain)
    elif browser == 'edge':
        cookie = browser_cookie3.edge(domain_name=domain)
    elif browser == 'safari':
        cookie = browser_cookie3.safari(domain_name=domain)
    elif browser == 'opera':
        cookie = browser_cookie3.opera(domain_name=domain)
    elif browser == 'brave':
        cookie = browser_cookie3.brave(domain_name=domain)
    else:
        raise ValueError('Invalid browser specified')

    return cookie