# -*- coding: utf-8 -*-
"""NVML Proxy Package

Package cho NVML Proxy functionality - bao gồm daemon, interface và plugin wrapper.
"""

from .nvml_proxy_interface import INVMLProxyPlugin
from .nvml_proxy_plugin import NVMLProxyPlugin

__all__ = ['INVMLProxyPlugin', 'NVMLProxyPlugin']